from datetime import date
from decimal import Decimal as D
from fastapi import HTTPException
import pytest
from app.models.accounting_setting import AccountingSetting
from app.models.chart_of_account import ChartOfAccount
from app.models.journal_line import JournalLine
from app.models.general_ledger import GeneralLedger
from app.models.inventory import Inventory
from app.models.stock_movement import StockMovement
from app.schemas.sales_transaction import SalesTransactionCreate, SalesTransactionPost
from app.services.sales_transaction_service import SalesTransactionService as Service
from app.services.pos_tax import pbjt_account
from test_pos_sell_catalog_1021 import products, menu
from test_finance_delivery_1007 import db, ADMIN


def setup(s, accounts, monkeypatch):
    monkeypatch.setattr('app.services.sales_transaction_service.ActivityService.log',lambda **kw:None)
    for key, account in [('POS_CASH_ACCOUNT',accounts[2]),('POS_SALES_REVENUE_ACCOUNT',accounts[0]),('POS_TAX_PAYABLE_ACCOUNT',accounts[3])]:
        s.add(AccountingSetting(setting_key=key,account_id=account.id))
    liability=ChartOfAccount(account_number='200-400-100',account_name='Hutang PBJT - Hotel dan Resto, Catering',account_type='LIABILITY',normal_balance='CREDIT',is_posting=True,is_active=True)
    s.add(liability)
    s.add(ChartOfAccount(account_number='200-400-101',account_name='Hutang PBJT - Listrik',account_type='LIABILITY',normal_balance='CREDIT',is_posting=True,is_active=True))
    s.commit()
    return liability


def test_pbjt_menu_posts_to_existing_payable_and_preserves_snapshot(db,monkeypatch):
    s,unit,loc,dept,accounts=db
    liability=setup(s,accounts,monkeypatch)
    p,_,_=products(s);p.pbjt_rate=10;p.selling_price=100000;p.service_charge_rate=0;s.commit()
    entry=menu(s,None)['items'][0]
    assert entry['sale_available'] and entry['tax_type']=='PBJT' and entry['tax_rate']==10
    tx=Service.create(s,data=SalesTransactionCreate(location_id=loc.id,sale_date=date(2026,1,5),items=[dict(product_id=p.id,quantity=1)]),user=ADMIN)
    assert tx.total_amount==110000 and tx.lines[0].tax_account_id==liability.id
    p.pbjt_rate=15;p.selling_price=200000;s.commit()
    tx=Service.post(s,transaction_id=tx.id,data=SalesTransactionPost(payment_received=110000),user=ADMIN)
    assert tx.total_amount==110000 and tx.lines[0].tax_rate==10
    lines=s.query(JournalLine).all()
    assert {l.account_id:(l.debit,l.credit) for l in lines}=={accounts[2].id:(D(110000),D(0)),accounts[0].id:(D(0),D(100000)),liability.id:(D(0),D(10000))}
    assert s.query(GeneralLedger).count()==3
    assert s.query(Inventory).count()==s.query(StockMovement).count()==0
    with pytest.raises(HTTPException): Service.post(s,transaction_id=tx.id,data=SalesTransactionPost(payment_received=110000),user=ADMIN)
    assert s.query(JournalLine).count()==3


def test_pbjt_discount_service_and_separate_legacy_tax(db,monkeypatch):
    s,unit,loc,dept,accounts=db
    liability=setup(s,accounts,monkeypatch)
    p,_,other=products(s)
    p.pbjt_rate=10;p.selling_price=100;p.service_charge_rate=5
    other.catalog_type='CATERING';other.is_taxable=True;other.tax_rate=10;other.service_charge_rate=0
    s.commit()
    tx=Service.create(s,data=SalesTransactionCreate(location_id=loc.id,sale_date=date(2026,1,5),items=[dict(product_id=p.id,quantity=1),dict(product_id=other.id,quantity=1)]),user=ADMIN)
    tx=Service.post(s,transaction_id=tx.id,data=SalesTransactionPost(payment_received=300,discount_amount=20),user=ADMIN)
    assert tx.lines[0].tax_amount==D('9.50') # (100 - 10 + 5) * 10%
    assert tx.total_amount==D('204.50')
    credits={l.account_id:l.credit for l in s.query(JournalLine).all()}
    assert credits[liability.id]==D('9.50') and credits[accounts[3].id]==10
    assert sum(l.debit for l in s.query(JournalLine))==sum(l.credit for l in s.query(JournalLine))


def test_pbjt_mapping_missing_ambiguous_and_wrong_type_do_not_post(db,monkeypatch):
    s,unit,loc,dept,accounts=db
    monkeypatch.setattr('app.services.sales_transaction_service.ActivityService.log',lambda **kw:None)
    p,_,_=products(s);p.pbjt_rate=10;s.commit()
    assert not menu(s,None)['items'][0]['sale_available']
    with pytest.raises(HTTPException): pbjt_account(s)
    for i in range(2):
        s.add(ChartOfAccount(account_number=f'PBJT-{i}',account_name=f'Hutang PBJT {i}',account_type='LIABILITY',normal_balance='CREDIT',is_posting=True,is_active=True))
    s.commit()
    with pytest.raises(HTTPException): pbjt_account(s)
    s.add(AccountingSetting(setting_key='POS_PBJT_PAYABLE_ACCOUNT',account_id=accounts[0].id));s.commit()
    with pytest.raises(HTTPException): pbjt_account(s)
    assert s.query(JournalLine).count()==s.query(GeneralLedger).count()==0
