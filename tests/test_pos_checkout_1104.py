from decimal import Decimal as D
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from test_finance_delivery_1007 import db,ADMIN
from test_pos_operations import hotel,prepare,create
from app.schemas.pos_checkout import CheckoutConfigurationSave,CheckoutConfiguration
from app.schemas.sales_transaction import SalesTransactionUpdate,SalesTransactionPost
from app.services.sales_transaction_service import SalesTransactionService as Sales
from app.services.pos_checkout import choices,save,discount_amount
from app.models.chart_of_account import ChartOfAccount
from app.models.general_ledger import GeneralLedger
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.stock_movement import StockMovement
from app.models.opening_balance import OpeningBalance
from app.models.pos_operations import PosOutletPolicy, PosCashierSession
from app.services import pos_operations as ops


def configure(hotel):
    s,scope,p,accounts,_=hotel
    prepare(hotel,'COUNTER')
    bank=ChartOfAccount(account_number='100-110-NEW',account_name='Outlet Card Clearing',account_type='ASSET',normal_balance='DEBIT',is_active=True,is_posting=True)
    s.add(bank);s.commit()
    current=choices(s,ADMIN,**scope,management=True)
    config={'payment_methods':[{'method':'CASH','enabled':True,'account_id':accounts[2].id},{'method':'CARD','enabled':True,'account_id':bank.id},{'method':'BANK_TRANSFER','enabled':False,'account_id':None}],
        'discount_presets':[{'id':'member','name':'Member','kind':'PERCENT','value':10,'enabled':True},{'id':'voucher','name':'Voucher','kind':'FIXED','value':15000,'enabled':True},{'id':'disabled','name':'Disabled','kind':'PERCENT','value':20,'enabled':False}]}
    result=save(s,ADMIN,CheckoutConfigurationSave(**scope,version=current['version'],configuration=config))
    shift=s.query(PosCashierSession).one()
    return s,scope,p,accounts,bank,result,shift


def test_preset_discount_updates_pbjt_posts_selected_account_once_and_snapshots(hotel):
    s,scope,p,accounts,bank,settings,shift=configure(hotel)
    tx=create(hotel,shift,discount_preset_id='member',checkout_version=settings['version'])
    identity=(tx.id,tx.transaction_number)
    assert tx.discount_amount==10000 and tx.tax_amount==9000 and tx.total_amount==99000
    assert tx.checkout_snapshot['discount_preset']['name']=='Member'
    tx=Sales.post(s,transaction_id=tx.id,data=SalesTransactionPost(payment_method='CARD',checkout_version=settings['version'],discount_preset_id='member'),user=ADMIN)
    assert tx.total_amount==99000 and (tx.id,tx.transaction_number)==identity
    debit=s.query(JournalLine).filter(JournalLine.journal_entry_id==tx.journal_entry_id,JournalLine.debit>0).one()
    assert debit.account_id==bank.id and debit.debit==99000
    assert tx.checkout_snapshot['payment_account_id']==bank.id
    saved=dict(tx.checkout_snapshot)
    config=settings['configuration'];config['discount_presets'][0]['value']='25'
    config['payment_methods'][1]['account_id']=accounts[2].id
    save(s,ADMIN,CheckoutConfigurationSave(**scope,version=settings['version'],configuration=config))
    s.refresh(tx)
    assert tx.checkout_snapshot==saved and tx.total_amount==99000
    count=s.query(GeneralLedger).count()
    with pytest.raises(HTTPException):Sales.post(s,transaction_id=tx.id,data=SalesTransactionPost(payment_method='CARD',checkout_version=settings['version']),user=ADMIN)
    assert s.query(GeneralLedger).count()==count
    assert s.query(StockMovement).count()==s.query(OpeningBalance).count()==0


def test_cash_change_shift_totals_follow_discounted_receipt(hotel):
    s,scope,p,accounts,bank,settings,shift=configure(hotel)
    tx=create(hotel,shift,discount_preset_id='voucher',checkout_version=settings['version'])
    assert tx.total_amount==93500
    Sales.post(s,transaction_id=tx.id,data=SalesTransactionPost(payment_received=100000,checkout_version=settings['version']),user=ADMIN)
    assert tx.change_amount==6500 and tx.discount_amount==15000
    summary=ops.shift_report(s,shift)
    assert summary['payments']['CASH']==93500 and summary['expected_cash']==103500


@pytest.mark.parametrize('case',['manual','forged','disabled-method','stale','missing-version'])
def test_invalid_checkout_never_posts(hotel,case):
    s,scope,p,accounts,bank,settings,shift=configure(hotel)
    tx=create(hotel,shift,discount_preset_id='member',checkout_version=settings['version'])
    body={'payment_received':110000,'checkout_version':settings['version']}
    if case=='manual':body.update(discount_preset_id=None,discount_amount=1234)
    elif case=='forged':body['discount_amount']=99999
    elif case=='disabled-method':body['payment_method']='BANK_TRANSFER'
    elif case=='stale':body['checkout_version']='stale-version'
    elif case=='missing-version':body.pop('checkout_version')
    with pytest.raises(HTTPException):Sales.post(s,transaction_id=tx.id,data=SalesTransactionPost(**body),user=ADMIN)
    s.rollback()
    assert tx.status=='DRAFT' and tx.journal_entry_id is None and not s.query(GeneralLedger).count()


@pytest.mark.parametrize('preset',['disabled','foreign-outlet-id'])
def test_unknown_or_inactive_presets_rejected(hotel,preset):
    s,scope,p,accounts,bank,settings,shift=configure(hotel)
    with pytest.raises(HTTPException):create(hotel,shift,discount_preset_id=preset,checkout_version=settings['version'])
    s.rollback();assert not s.query(GeneralLedger).count()


def test_configuration_changed_while_order_open_requires_refresh_and_draft_review(hotel):
    s,scope,p,accounts,bank,settings,shift=configure(hotel)
    tx=create(hotel,shift,discount_preset_id='member',checkout_version=settings['version'])
    config=settings['configuration'];config['discount_presets'][0]['value']='20'
    changed=save(s,ADMIN,CheckoutConfigurationSave(**scope,version=settings['version'],configuration=config))
    assert changed['version']!=settings['version']
    with pytest.raises(HTTPException):Sales.post(s,transaction_id=tx.id,data=SalesTransactionPost(payment_received=110000,checkout_version=settings['version']),user=ADMIN)
    s.rollback()
    with pytest.raises(HTTPException):Sales.post(s,transaction_id=tx.id,data=SalesTransactionPost(payment_received=110000,checkout_version=changed['version']),user=ADMIN)
    s.rollback()
    Sales.update(s,transaction=tx,data=SalesTransactionUpdate(items=[{'product_id':p.id,'quantity':1,'unit_price':100000}],discount_preset_id='member',checkout_version=changed['version']),user=ADMIN)
    assert tx.total_amount==88000
    Sales.post(s,transaction_id=tx.id,data=SalesTransactionPost(payment_received=100000,checkout_version=changed['version']),user=ADMIN)
    assert tx.status=='POSTED'


def test_only_finance_can_configure_and_stale_settings_never_overwrite(hotel):
    s,scope,p,accounts,bank,settings,shift=configure(hotel)
    cashier=SimpleNamespace(**{**vars(ADMIN),'roles':[SimpleNamespace(name='CASHIER',permissions=[SimpleNamespace(code='pos.sell'),SimpleNamespace(code='pos.view')])]})
    assert choices(s,cashier,**scope)['configuration']['payment_methods']
    with pytest.raises(HTTPException):choices(s,cashier,**scope,management=True)
    with pytest.raises(HTTPException):save(s,cashier,CheckoutConfigurationSave(**scope,version=settings['version'],configuration=settings['configuration']))
    with pytest.raises(HTTPException):save(s,ADMIN,CheckoutConfigurationSave(**scope,version='old',configuration=settings['configuration']))
    assert s.query(PosOutletPolicy).one().checkout_settings==settings['configuration']


def test_mapping_must_remain_active_posting_debit_asset_at_settlement(hotel):
    s,scope,p,accounts,bank,settings,shift=configure(hotel)
    bad=settings['configuration'];bad['payment_methods'][1]['account_id']=accounts[0].id
    with pytest.raises(HTTPException):save(s,ADMIN,CheckoutConfigurationSave(**scope,version=settings['version'],configuration=bad))
    s.rollback()
    tx=create(hotel,shift,checkout_version=settings['version'])
    bank.is_active=False;s.commit()
    with pytest.raises(HTTPException):Sales.post(s,transaction_id=tx.id,data=SalesTransactionPost(payment_method='CARD',checkout_version=settings['version']),user=ADMIN)
    s.rollback();assert tx.status=='DRAFT' and not s.query(GeneralLedger).count()


def test_discount_validation_and_rounding_do_not_invent_balancing_entries():
    with pytest.raises(ValidationError):CheckoutConfiguration(payment_methods=[],discount_presets=[])
    from app.schemas.pos_checkout import DiscountPreset
    with pytest.raises(ValidationError):DiscountPreset(id='bad',name='Bad',kind='PERCENT',value=101)
    assert discount_amount(D('99.95'),{'kind':'PERCENT','value':'7.5'})==D('7.50')
    assert discount_amount(D('20'),{'kind':'FIXED','value':'100'})==D('20.00')
