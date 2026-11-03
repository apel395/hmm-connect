from decimal import Decimal
import pytest
from fastapi import HTTPException
from test_partial_inventory_returns import setup_return, new_return, invoice
from test_store_request_flow import store_db
from app.models.inventory import Inventory
from app.models.inventory_return import InventoryReturnEvent
from app.models.journal_entry import JournalEntry
from app.models.general_ledger import GeneralLedger
from app.models.stock_movement import StockMovement
from app.models.chart_of_account import ChartOfAccount
from app.schemas.inventory_return import ReturnCreditInput, SupplierCreditUseInput, ReturnEventInput, ReplacementInput
from app.services import inventory_return_service as returns
from app.services import inventory_return_completion as service
from app.api.v1.inventory_returns import credit_use, reverse_posted, commit_result


def credit(fixture):
    db, source, accounts, user, _, today = fixture
    inv = invoice(fixture, 100)
    row = new_return(fixture, 'AP_CREDIT')
    returns.post_return(db, row.id, user)
    returns.settle_credit(db, row.id, ReturnCreditInput(supplier_invoice_id=inv.id, credit_date=today,
        credit_reference='CN', net_amount=30, supplier_credit_account_id=accounts[1].id,
        variance_account_id=source.items[0].product.cogs_account_id), user)
    db.commit()
    return row, inv


def target(fixture):
    from app.models.supplier_invoice import SupplierInvoice, SupplierInvoiceLine
    db, source, accounts, user, _, today = fixture
    inv = SupplierInvoice(internal_invoice_number='INV-TARGET',supplier_invoice_number='Supplier-Target',
        supplier_id=source.supplier_id, invoice_date=today, status='POSTED', currency='IDR',
        business_unit_id=source.business_unit_id, location_id=source.location_id, department_id=source.department_id,
        subtotal=100,tax_amount=0,total_amount=100,paid_amount=0)
    inv.lines=[SupplierInvoiceLine(product_id=source.items[0].product_id, description='Target goods', quantity=10,
        unit_price=10,line_amount=100,account_id=source.items[0].product.inventory_account_id)]
    db.add(inv);db.commit()
    return inv


def event_data(fixture, **kw):
    return ReturnEventInput(event_date=fixture[-1],reference='Correction',reason='Wrong document',**kw)


def use_data(fixture, inv=None, amount=20, **kw):
    return SupplierCreditUseInput(event_date=fixture[-1],reference='CN use',reason='Apply supplier credit',
        kind='APPLY',amount=amount,supplier_invoice_id=inv.id if inv else None,**kw)


def test_credit_apply_retry_reverse_and_refund(setup_return):
    db, source, accounts, user, _, today = setup_return
    row, original = credit(setup_return)
    inv = target(setup_return)
    data = use_data(setup_return,inv)
    service.apply_credit(db,row.id,data,user);db.commit()
    assert inv.adjustment_amount == 20 and inv.paid_amount == 0 and inv.balance_amount == 80
    assert service.remaining_credit(db,row) == 10
    service.apply_credit(db,row.id,data,user);db.commit()
    assert db.query(InventoryReturnEvent).count() == 1
    assert original.paid_amount == 100
    with pytest.raises(HTTPException): returns.guard_invoice(db,inv.id)
    with pytest.raises(HTTPException): service.apply_credit(db,row.id,use_data(setup_return,inv,11),user)
    db.rollback()
    use = db.query(InventoryReturnEvent).one()
    with pytest.raises(HTTPException): service.reverse_return(db,row.id,event_data(setup_return),user)
    db.rollback()
    reverse = event_data(setup_return)
    service.reverse_use(db,row.id,use.id,reverse,user);db.commit()
    service.reverse_use(db,row.id,use.id,reverse,user);db.commit()
    assert inv.adjustment_amount == 0 and inv.balance_amount == 100
    assert service.remaining_credit(db,row) == 30
    returns.guard_invoice(db,inv.id)
    bank = ChartOfAccount(account_number='BANK-RET',account_name='Bank',account_type='ASSET',normal_balance='DEBIT',
        account_subtype='BANK',is_active=True,is_posting=True)
    db.add(bank);db.commit()
    refund = SupplierCreditUseInput(event_date=today,reference='Refund bank transfer',reason='Supplier refund',
        kind='REFUND',amount=30,cash_account_id=bank.id)
    service.apply_credit(db,row.id,refund,user);db.commit()
    assert service.remaining_credit(db,row) == 0
    refund_event=db.query(InventoryReturnEvent).filter_by(kind='REFUND').one()
    entry=db.get(JournalEntry,refund_event.journal_entry_id)
    assert {(l.account_id,l.debit,l.credit) for l in entry.lines}=={(bank.id,Decimal(30),Decimal(0)),(accounts[1].id,Decimal(0),Decimal(30))}
    service.reverse_use(db,row.id,refund_event.id,event_data(setup_return),user);db.commit()
    assert service.remaining_credit(db,row)==30
    original_journal_ids={j.id for j in db.query(JournalEntry)}
    service.reverse_return(db,row.id,event_data(setup_return),user);db.commit()
    assert row.status=='VOID' and service.remaining_credit(db,row)==0
    assert db.query(Inventory).filter_by(product_id=source.items[0].product_id).one().quantity==10
    assert all(db.get(JournalEntry,i).status=='POSTED' for i in original_journal_ids)
    assert sum(l.debit-l.credit for l in db.query(GeneralLedger))==0


@pytest.mark.parametrize('replaced',[0,1,3])
def test_return_reversal_with_partial_or_complete_replacement(setup_return,replaced):
    db, source, accounts, user, _, today=setup_return
    row=new_return(setup_return)
    returns.post_return(db,row.id,user);db.commit()
    if replaced:
        returns.replace_goods(db,row.id,ReplacementInput(received_date=today,delivery_note='Replacement',
            items=[{'return_item_id':row.items[0].id,'quantity':replaced}]),user);db.commit()
    before=db.query(StockMovement).count()
    data=event_data(setup_return)
    service.reverse_return(db,row.id,data,user);db.commit()
    stock=db.query(Inventory).filter_by(product_id=source.items[0].product_id).one()
    assert stock.quantity==10 and stock.average_cost==Decimal('12.3456')
    assert row.status=='VOID'
    assert db.query(StockMovement).count()==before+(replaced<3)
    assert returns.returned_quantities(db,source.id)=={}
    assert returns.serialize(db,row)['clearing_balance']==0
    count=db.query(JournalEntry).count()
    service.reverse_return(db,row.id,data,user);db.commit()
    assert db.query(JournalEntry).count()==count
    for account_id in [accounts[0].id,source.items[0].product.inventory_account_id]:
        assert sum(l.debit-l.credit for l in db.query(GeneralLedger).filter_by(account_id=account_id))==0


def test_unpaid_credit_reversal_restores_ap_and_does_not_change_payment(setup_return):
    db,source,accounts,user,_,today=setup_return
    inv=invoice(setup_return,90)
    row=new_return(setup_return,'AP_CREDIT')
    returns.post_return(db,row.id,user)
    returns.settle_credit(db,row.id,ReturnCreditInput(supplier_invoice_id=inv.id,credit_date=today,credit_reference='CN',
        net_amount=30,supplier_credit_account_id=accounts[1].id,variance_account_id=source.items[0].product.cogs_account_id),user);db.commit()
    assert inv.adjustment_amount==10
    service.reverse_return(db,row.id,event_data(setup_return),user);db.commit()
    assert inv.adjustment_amount==0 and inv.paid_amount==90 and inv.balance_amount==10
    returns.guard_invoice(db,inv.id)


def test_credit_usage_rejects_wrong_scope_account_amount_and_payload_reuse(setup_return):
    db,source,accounts,user,_,today=setup_return
    row,_=credit(setup_return)
    inv=target(setup_return)
    from app.models.supplier import Supplier
    other=Supplier(code="OTHER-RET",name="Other supplier")
    db.add(other);db.flush()
    inv.supplier_id=other.id
    with pytest.raises(HTTPException): service.apply_credit(db,row.id,use_data(setup_return,inv),user)
    db.rollback()
    with pytest.raises(HTTPException): service.apply_credit(db,row.id,use_data(setup_return,inv,31),user)
    db.rollback()
    data=use_data(setup_return,inv,5)
    service.apply_credit(db,row.id,data,user);db.commit()
    with pytest.raises(HTTPException): service.apply_credit(db,row.id,data.model_copy(update={'amount':Decimal(6)}),user)
    db.rollback()
    bad=SupplierCreditUseInput(event_date=today,reference='Bad refund',reason='Wrong account',kind='REFUND',amount=1,cash_account_id=accounts[1].id)
    with pytest.raises(HTTPException): service.apply_credit(db,row.id,bad,user)
    db.rollback()
    assert service.remaining_credit(db,row)==25


def test_closed_period_and_permission_enforcement(setup_return):
    db,source,accounts,user,requester,today=setup_return
    row,_=credit(setup_return)
    inv=target(setup_return)
    with pytest.raises(HTTPException) as err: credit_use(row.id,use_data(setup_return,inv),db,requester)
    assert err.value.status_code==403
    with pytest.raises(HTTPException) as err: reverse_posted(row.id,event_data(setup_return),db,requester)
    assert err.value.status_code==403
    from app.models.fiscal_period import FiscalPeriod
    period=db.query(FiscalPeriod).one();period.is_closed=True;period.is_open=False;db.commit()
    before=db.query(JournalEntry).count()
    with pytest.raises(HTTPException): service.apply_credit(db,row.id,use_data(setup_return,inv),user)
    db.rollback()
    with pytest.raises(HTTPException): service.reverse_return(db,row.id,event_data(setup_return),user)
    db.rollback()
    assert db.query(JournalEntry).count()==before and row.status=='POSTED'


def test_failure_rolls_back_event_journal_stock_and_adjustment(setup_return,monkeypatch):
    db,source,accounts,user,_,today=setup_return
    row,_=credit(setup_return)
    inv=target(setup_return)
    before=db.query(JournalEntry).count()
    def fail(*args): raise RuntimeError('forced failure after journal')
    monkeypatch.setattr(service,'_sync_invoice_payable',fail)
    with pytest.raises(RuntimeError):
        commit_result(db,lambda:service.apply_credit(db,row.id,use_data(setup_return,inv),user))
    assert db.query(InventoryReturnEvent).count()==0 and db.query(JournalEntry).count()==before
    assert inv.adjustment_amount==0 and service.remaining_credit(db,row)==30


def test_incomplete_stock_history_blocks_reversal_atomically(setup_return):
    db,source,accounts,user,_,today=setup_return
    row=new_return(setup_return)
    returns.post_return(db,row.id,user);db.commit()
    movement=db.query(StockMovement).one();db.delete(movement);db.commit()
    before=db.query(JournalEntry).count()
    with pytest.raises(HTTPException):
        commit_result(db,lambda:service.reverse_return(db,row.id,event_data(setup_return),user))
    assert row.status=='POSTED' and db.query(JournalEntry).count()==before
    assert db.query(InventoryReturnEvent).count()==0
    assert db.query(Inventory).filter_by(product_id=source.items[0].product_id).one().quantity==7


def test_reversal_history_keeps_period_report_and_filtered_return_totals(setup_return):
    from app.api.v1.inventory_period_report import period_report
    db,source,accounts,user,_,today=setup_return
    row=new_return(setup_return)
    returns.post_return(db,row.id,user);db.commit()
    service.reverse_return(db,row.id,event_data(setup_return),user);db.commit()
    result=period_report(date_from=today,date_to=today,warehouse_id=source.warehouse_id,
        business_unit_id=None,location_id=None,search=None,page=1,page_size=50,db=db,user=user)
    item=next(i for i in result['items'] if i['product_id']==source.items[0].product_id)
    assert item['return_quantity']==0 and item['return_value']==0
    assert item['opening_quantity']==item['closing_quantity']==10


def test_credit_invoice_lookup_shows_only_accounted_scoped_outstanding_invoices(setup_return):
    from app.api.v1.inventory_returns import credit_invoices
    db,source,accounts,user,_,today=setup_return
    row,_=credit(setup_return)
    inv=target(setup_return)
    # API finance guard is tested separately; use a finance-authorized actor here.
    from types import SimpleNamespace
    admin=SimpleNamespace(id=user.id,roles=[SimpleNamespace(name='SYSTEM_ADMINISTRATOR')],location_id=None,
        default_location_id=None,department_id=None,default_department_id=None,default_business_unit_id=None)
    result=credit_invoices(row.id,search='INV-TARGET',page=1,db=db,user=admin)
    assert result['items']==[{'id':inv.id,'number':'INV-TARGET','balance':Decimal(100)}]
    inv.status='DRAFT';db.commit()
    assert credit_invoices(row.id,search='',page=1,db=db,user=admin)['items']==[]


def test_reversed_credit_does_not_consume_source_invoice_credit_limit(setup_return):
    db,source,accounts,user,_,today=setup_return
    row,inv=credit(setup_return)
    service.reverse_return(db,row.id,event_data(setup_return),user);db.commit()
    # The original source remains protected even after reversal for audit history.
    with pytest.raises(HTTPException): returns.guard_receipt(db,source.id)
    new=new_return(setup_return,'AP_CREDIT',quantity='8')
    returns.post_return(db,new.id,user)
    returns.settle_credit(db,new.id,ReturnCreditInput(supplier_invoice_id=inv.id,credit_date=today,
        credit_reference='Correct CN',net_amount=80,supplier_credit_account_id=accounts[1].id,
        variance_account_id=source.items[0].product.cogs_account_id),user);db.commit()
    assert service.remaining_credit(db,new)==80
