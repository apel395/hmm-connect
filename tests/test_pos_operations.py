from datetime import date
from decimal import Decimal as D
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from app.models.accounting_setting import AccountingSetting
from app.models.business_unit import BusinessUnit
from app.models.department import Department
from app.models.department_outlet import DepartmentOutlet
from app.models.location_department import LocationDepartment
from app.models.sales_transaction import SalesTransaction
from app.models.pos_operations import PosTable, PosCashierSession
from app.models.journal_line import JournalLine
from app.models.general_ledger import GeneralLedger
from app.models.stock_movement import StockMovement
from app.schemas.pos_operations import OutletPolicyIn, ShiftOpen, ShiftClose, TableIn
from app.schemas.sales_transaction import SalesTransactionCreate, SalesTransactionUpdate, SalesTransactionPost, SalesTransactionVoid
from app.services.sales_transaction_service import SalesTransactionService as Sales
from app.services import pos_operations as ops
from app.api.v1.pos_metadata import update_pos_metadata, PosMetadataIn
from app.api.v1.pos_operations import report, context
from test_finance_delivery_1007 import db, ADMIN
from test_pos_ar_invoices import invoice_setup


@pytest.fixture
def hotel(db,monkeypatch):
    s,invoice,customer,ar,accounts,pbjt=invoice_setup(db,monkeypatch)
    unit=s.get(BusinessUnit,invoice.business_unit_id);unit.name='Hotel Test'
    parent=Department(code='FNB',name='Food and Beverage',business_unit_id=unit.id,is_active=True)
    s.add(AccountingSetting(setting_key='POS_CARD_ACCOUNT',account_id=accounts[2].id))
    s.add(parent);s.flush()
    s.add_all([DepartmentOutlet(department_id=invoice.department_id,parent_department_id=parent.id),LocationDepartment(location_id=invoice.location_id,department_id=parent.id)])
    product=invoice.lines[0].product;product.catalog_type='HOTEL';s.commit()
    scope=dict(location_id=invoice.location_id,department_id=invoice.department_id)
    monkeypatch.setattr('app.services.pos_operations.ActivityService.log',lambda **kw:None)
    return s,scope,product,accounts,invoice


def prepare(hotel,mode='TABLE'):
    s,scope,*_=hotel
    ops.set_policy(s,OutletPolicyIn(**scope,order_mode=mode),ADMIN)
    shift=ops.open_shift(s,ShiftOpen(**scope,opening_cash=10000),ADMIN)
    table=ops.save_table(s,TableIn(**scope,name='T-01'),ADMIN)
    return shift,table


def create(hotel,shift,table=None,key='test-order-0001',**kw):
    s,scope,p,*_=hotel
    return Sales.create(s,data=SalesTransactionCreate(**scope,cashier_session_id=shift.id,pos_table_id=table.id if table else None,order_request_key=key,sale_date=date(2026,1,5),items=[dict(product_id=p.id,quantity=1)],**kw),user=ADMIN)


def test_table_reservation_edit_settle_once_and_cash_close(hotel):
    s,scope,p,accounts,_=hotel;shift,table=prepare(hotel)
    tx=create(hotel,shift,table)
    assert context(**scope,db=s,user=ADMIN)['tables'][0]['status']=='OCCUPIED'
    retry=create(hotel,shift,table)
    assert retry.id==tx.id
    with pytest.raises(HTTPException):create(hotel,shift,table,key='another-order-0002')
    with pytest.raises(HTTPException):ops.save_table(s,TableIn(**scope,name='Renamed',is_active=False),ADMIN,table.id)
    with pytest.raises(HTTPException):ops.close_shift(s,shift,ShiftClose(counted_cash=10000),ADMIN)
    number=tx.transaction_number
    Sales.update(s,transaction=tx,data=SalesTransactionUpdate(revenue_account_id=accounts[0].id,items=[dict(product_id=p.id,quantity=2,unit_price=100000)]),user=ADMIN)
    assert tx.transaction_number==number and tx.total_amount==220000
    Sales.post(s,transaction_id=tx.id,data=SalesTransactionPost(revenue_account_id=accounts[0].id,payment_received=230000),user=ADMIN)
    assert tx.change_amount==10000
    assert context(**scope,db=s,user=ADMIN)['tables'][0]['status']=='AVAILABLE'
    with pytest.raises(HTTPException):Sales.post(s,transaction_id=tx.id,data=SalesTransactionPost(payment_received=220000),user=ADMIN)
    assert s.query(GeneralLedger).count()==3 and s.query(StockMovement).count()==0
    before=s.query(JournalLine).count()
    with pytest.raises(HTTPException):ops.close_shift(s,shift,ShiftClose(counted_cash=229000),ADMIN)
    closed=ops.close_shift(s,shift,ShiftClose(counted_cash=229000,difference_reason='Cash counted short'),ADMIN)
    assert closed['expected_cash']==230000 and closed['cash_difference']==-1000
    assert s.query(JournalLine).count()==before # no balancing journal or opening-balance write
    with pytest.raises(HTTPException):ops.close_shift(s,shift,ShiftClose(counted_cash=230000),ADMIN)
    with pytest.raises(HTTPException):create(hotel,shift,table,key='closed-shift-0003')


def test_counter_optional_table_event_requires_name_and_no_table(hotel):
    s,scope,p,accounts,_=hotel;shift,table=prepare(hotel,'COUNTER')
    counter=create(hotel,shift)
    assert counter.table_number is None and counter.order_mode=='COUNTER'
    update_pos_metadata(counter.id,PosMetadataIn(transaction_type='POS'),s,ADMIN)
    with pytest.raises(HTTPException):update_pos_metadata(counter.id,PosMetadataIn(transaction_type='INVOICE'),s,ADMIN)
    Sales.void(s,transaction_id=counter.id,data=SalesTransactionVoid(reason='Test cancellation'),user=ADMIN)
    ops.close_shift(s,shift,ShiftClose(counted_cash=10000),ADMIN)
    ops.set_policy(s,OutletPolicyIn(**scope,order_mode='EVENT'),ADMIN)
    event_shift=ops.open_shift(s,ShiftOpen(**scope,opening_cash=0),ADMIN)
    with pytest.raises(HTTPException):create(hotel,event_shift,key='event-empty-0001')
    with pytest.raises(HTTPException):create(hotel,event_shift,table,key='event-table-0002',event_name='Annual dinner')
    event=create(hotel,event_shift,key='event-valid-0003',event_name='Annual dinner')
    assert event.event_name=='Annual dinner' and event.pos_table_id is None
    Sales.post(s,transaction_id=event.id,data=SalesTransactionPost(revenue_account_id=accounts[0].id,payment_method='CARD'),user=ADMIN)
    closed=ops.close_shift(s,event_shift,ShiftClose(counted_cash=0),ADMIN)
    assert closed['payments']['CARD']==110000 and closed['expected_cash']==0


def test_scoped_tables_shifts_cashier_and_policy_cannot_be_bypassed(hotel):
    s,scope,p,accounts,_=hotel;shift,table=prepare(hotel)
    with pytest.raises(HTTPException):ops.open_shift(s,ShiftOpen(**scope,opening_cash=0),ADMIN)
    with pytest.raises(HTTPException):ops.set_policy(s,OutletPolicyIn(**scope,order_mode='EVENT'),ADMIN)
    with pytest.raises(HTTPException):create(hotel,shift,key='table-required-1')
    other=SimpleNamespace(**{**vars(ADMIN),'id':99})
    with pytest.raises(HTTPException):ops.shift_access(s,shift.id,other,lock=True,owner=True)
    scoped=SimpleNamespace(**{**vars(ADMIN),'roles':[],'default_location_id':999})
    with pytest.raises(HTTPException):ops.outlet(s,scoped,**scope)
    with pytest.raises(HTTPException):ops.outlet(s,ADMIN,scope['location_id'],999)
    tx=create(hotel,shift,table)
    with pytest.raises(HTTPException):create(hotel,shift,table,event_name='changed payload')
    # The database itself enforces active-table uniqueness, independent of API checks.
    dupe=SalesTransaction(transaction_number='DUP',status='DRAFT',transaction_type='POS',sale_date=date(2026,1,5),created_by_id=1,pos_table_id=table.id)
    s.add(dupe)
    with pytest.raises(IntegrityError):s.flush()
    s.rollback()
    assert s.get(SalesTransaction,tx.id).status=='DRAFT'


def test_daily_outlet_report_tax_service_and_payment_methods(hotel):
    s,scope,p,accounts,_=hotel;shift,table=prepare(hotel,'COUNTER')
    p.service_charge_rate=5;s.commit()
    for n,method in enumerate(('CASH','CARD','BANK_TRANSFER')):
        tx=create(hotel,shift,key=f'report-order-{n}')
        Sales.post(s,transaction_id=tx.id,data=SalesTransactionPost(revenue_account_id=accounts[0].id,payment_method=method,payment_received=120000),user=ADMIN)
    result=report(**scope,date_from=date(2026,1,1),date_to=date(2026,1,31),db=s,user=ADMIN)
    assert result['sales']==3 and result['gross']==D('346500')
    assert result['pbjt']==31500 and result['service_charge']==15000
    assert result['payments']=={'CASH':D(115500),'CARD':D(115500),'BANK_TRANSFER':D(115500)}
    assert len(result['daily'])==1 and result['cashiers'][0]['gross']==result['gross']
    assert len(s.query(GeneralLedger).all())==9 and not s.query(StockMovement).count()
    assert report(**scope,date_from=date(2026,2,1),date_to=date(2026,2,28),db=s,user=ADMIN)['sales']==0
    with pytest.raises(HTTPException):report(**scope,date_from=date(2026,2,1),date_to=date(2026,1,1),db=s,user=ADMIN)


def test_exact_cash_required_and_ar_remains_outside_shift(hotel):
    s,scope,p,accounts,invoice=hotel;shift,table=prepare(hotel)
    tx=create(hotel,shift,table)
    with pytest.raises(HTTPException):Sales.post(s,transaction_id=tx.id,data=SalesTransactionPost(revenue_account_id=accounts[0].id,payment_received='109999.99'),user=ADMIN)
    assert tx.status=='DRAFT' and not s.query(GeneralLedger).count()
    Sales.post(s,transaction_id=invoice.id,data=SalesTransactionPost(),user=ADMIN)
    assert invoice.cashier_session_id is None and invoice.payment_received==0
    assert ops.shift_report(s,shift)['gross']==0
