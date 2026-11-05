from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.api.v1.sales import serialize_sale
from app.api.v1.pos_operations import context
from app.models.general_ledger import GeneralLedger
from app.models.journal_entry import JournalEntry
from app.models.stock_movement import StockMovement
from app.schemas.sales_transaction import SalesTransactionCreate, SalesTransactionUpdate, SalesTransactionPost
from app.services.sales_transaction_service import SalesTransactionService as Sales
from test_pos_operations import hotel, prepare, create
from test_finance_delivery_1007 import db, ADMIN


def test_table_guests_persist_edit_audit_retry_and_settle_once(hotel, monkeypatch):
    s,scope,p,accounts,_=hotel
    shift,table=prepare(hotel)
    logs=[]
    monkeypatch.setattr('app.services.sales_transaction_service.ActivityService.log',lambda **kw:logs.append(kw))
    tx=create(hotel,shift,table,guest_count=3)
    original_number=tx.transaction_number
    assert serialize_sale(tx)['guest_count']==3
    assert context(**scope,db=s,user=ADMIN)['orders'][0]['guest_count']==3
    assert logs[-1]['details']['guest_count']==3
    assert create(hotel,shift,table,guest_count=3).id==tx.id
    with pytest.raises(HTTPException,match='different order details'):
        create(hotel,shift,table,guest_count=4)
    before_total=tx.total_amount
    Sales.update(s,transaction=tx,data=SalesTransactionUpdate(guest_count=4,items=[dict(product_id=p.id,quantity=1)]),user=ADMIN)
    assert tx.guest_count==4 and tx.total_amount==before_total
    assert logs[-1]['before_data']['guest_count']==3 and logs[-1]['after_data']['guest_count']==4
    Sales.update(s,transaction=tx,data=SalesTransactionUpdate(items=[dict(product_id=p.id,quantity=2)]),user=ADMIN)
    assert tx.guest_count==4
    Sales.post(s,transaction_id=tx.id,data=SalesTransactionPost(revenue_account_id=accounts[0].id,payment_received=220000),user=ADMIN)
    journal_count=s.query(JournalEntry).count();gl_count=s.query(GeneralLedger).count()
    assert tx.status=='POSTED' and tx.guest_count==4 and tx.transaction_number==original_number
    assert tx.total_amount==Decimal('220000')
    with pytest.raises(HTTPException):
        Sales.update(s,transaction=tx,data=SalesTransactionUpdate(guest_count=5,items=[dict(product_id=p.id,quantity=2)]),user=ADMIN)
    with pytest.raises(HTTPException):
        Sales.post(s,transaction_id=tx.id,data=SalesTransactionPost(payment_received=220000),user=ADMIN)
    assert s.query(JournalEntry).count()==journal_count and s.query(GeneralLedger).count()==gl_count
    assert s.query(StockMovement).count()==0


def test_table_count_required_and_legacy_draft_correctable_without_recreation(hotel):
    s,_,p,accounts,_=hotel
    shift,table=prepare(hotel)
    with pytest.raises(HTTPException,match='number of guests'):
        create(hotel,shift,table,guest_count=None)
    s.rollback()
    tx=create(hotel,shift,table,guest_count=2)
    tx.guest_count=None;s.commit()  # Existing rows are intentionally not backfilled.
    jid=tx.journal_entry_id
    with pytest.raises(HTTPException,match='number of guests'):
        Sales.post(s,transaction_id=tx.id,data=SalesTransactionPost(revenue_account_id=accounts[0].id,payment_received=110000),user=ADMIN)
    assert tx.status=='DRAFT' and tx.journal_entry_id==jid
    with pytest.raises(HTTPException,match='number of guests'):
        Sales.update(s,transaction=tx,data=SalesTransactionUpdate(guest_count=None,items=[dict(product_id=p.id,quantity=1)]),user=ADMIN)
    Sales.update(s,transaction=tx,data=SalesTransactionUpdate(guest_count=2,items=[dict(product_id=p.id,quantity=1)]),user=ADMIN)
    assert tx.guest_count==2


@pytest.mark.parametrize('mode,extra',[('COUNTER',{}),('EVENT',{'event_name':'Annual dinner'})])
def test_counter_and_event_do_not_require_guests_or_tables(hotel,mode,extra):
    s,_,p,*_=hotel
    shift,_=prepare(hotel,mode)
    tx=create(hotel,shift,**extra)
    assert tx.guest_count is None and tx.pos_table_id is None
    Sales.update(s,transaction=tx,data=SalesTransactionUpdate(guest_count=8,items=[dict(product_id=p.id,quantity=1)]),user=ADMIN)
    assert tx.guest_count==8
    Sales.update(s,transaction=tx,data=SalesTransactionUpdate(guest_count=None,items=[dict(product_id=p.id,quantity=1)]),user=ADMIN)
    assert tx.guest_count is None


@pytest.mark.parametrize('value',[0,-1,1.5,True,'2',2147483648])
def test_invalid_guest_counts_rejected_on_create_and_update(value):
    for schema in (SalesTransactionCreate,SalesTransactionUpdate):
        with pytest.raises(ValidationError):schema(guest_count=value)


def test_catering_invoice_does_not_accept_hotel_guest_controls(hotel):
    s,_,p,_,invoice=hotel
    assert invoice.transaction_type=='INVOICE' and invoice.guest_count is None
    with pytest.raises(HTTPException,match='only to Hotel'):
        Sales.update(s,transaction=invoice,data=SalesTransactionUpdate(guest_count=2,items=[dict(product_id=p.id,quantity=1)]),user=ADMIN)
    assert invoice.guest_count is None


def test_database_rejects_nonpositive_count(hotel):
    s,*_=hotel
    shift,table=prepare(hotel)
    tx=create(hotel,shift,table)
    tx.guest_count=0
    with pytest.raises(IntegrityError):s.flush()
    s.rollback()
    assert tx.guest_count==2
