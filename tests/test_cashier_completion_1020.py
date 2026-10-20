from datetime import date
from decimal import Decimal
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.api.v1 import cashier, journals, cash_flow
from app.models.chart_of_account import ChartOfAccount
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.general_ledger import GeneralLedger
from app.models.fiscal_period import FiscalPeriod
from app.models.opening_balance import OpeningBalance
from app.services.cash_flow_service import CashFlowService
from test_finance_delivery_1007 import db, ADMIN


def data(db, operation='PAYMENT', amount=30):
    s,u,l,d,a=db
    bank=ChartOfAccount(account_number='100-BANK',account_name='Bank',account_type='ASSET',account_subtype='BANK',normal_balance='DEBIT',is_active=True,is_posting=True)
    s.add(bank);s.commit()
    return cashier.CashEntry(posting_date=date(2026,1,5),operation=operation,cash_account_id=a[2].id,
        counterpart_account_id=bank.id if operation in ('REPLENISHMENT','TRANSFER') else a[1].id,
        amount=amount,location_id=l.id,business_unit_id=u.id,department_id=d.id,reference_number='PC: V-1',description='Expense: meals')


def test_replenish_spend_return_and_book_balance_without_double_expense(db):
    s,u,l,d,a=db
    replenish=data(db,'REPLENISHMENT',100)
    first=cashier.create(replenish,s,ADMIN);cashier.post(first['id'],s,ADMIN);cashier.post(first['id'],s,ADMIN)
    spend=replenish.model_copy(update={'operation':'PAYMENT','counterpart_account_id':a[1].id,'amount':Decimal(30),'reference_number':'EXP-1'})
    second=cashier.create(spend,s,ADMIN);cashier.post(second['id'],s,ADMIN)
    refund=replenish.model_copy(update={'operation':'TRANSFER','amount':Decimal(10),'reference_number':'RETURN-1'})
    third=cashier.create(refund,s,ADMIN);cashier.post(third['id'],s,ADMIN)
    totals=CashFlowService(s).accounts_summary(date(2026,1,1),date(2026,1,31),location_id=l.id)
    petty=next(x for x in totals if x['account_id']==a[2].id)
    assert petty['total_inflow']==100 and petty['total_outflow']==40 and petty['closing_balance']==60
    assert sum(x.debit-x.credit for x in s.query(GeneralLedger).filter_by(account_id=a[1].id))==30
    assert s.query(GeneralLedger).count()==6 and s.query(JournalEntry).count()==3
    assert s.query(OpeningBalance).count()==0
    report=cashier.listing(date(2026,1,1),date(2026,1,31),petty_cash=True,page=1,page_size=100,db=s,user=ADMIN)
    assert report['total_items']==3


def test_edit_draft_keeps_identity_and_does_not_post_or_duplicate(db):
    s,u,l,d,a=db
    value=data(db)
    created=cashier.create(value,s,ADMIN)
    updated=cashier.update(created['id'],value.model_copy(update={'amount':Decimal(45)}),s,ADMIN)
    assert created['id']==updated['id'] and created['journal_number']==updated['journal_number']
    assert updated['entry']['reference_number']=='PC: V-1' and updated['entry']['description']=='Expense: meals'
    assert updated['total_debit']==45 and s.query(JournalEntry).count()==1 and s.query(JournalLine).count()==2
    assert not s.query(GeneralLedger).count()
    cashier.post(created['id'],s,ADMIN)
    with pytest.raises(HTTPException):cashier.update(created['id'],value,s,ADMIN)
    assert s.query(GeneralLedger).count()==2


def test_account_and_source_integrity_rechecked_from_both_post_routes(db):
    s,u,l,d,a=db
    value=data(db);created=cashier.create(value,s,ADMIN)
    a[2].account_subtype='OTHER';s.commit()
    for operation in (lambda:cashier.post(created['id'],s,ADMIN), lambda:journals.post_locked_journal(s,journal=s.get(JournalEntry,created['id']),user=ADMIN)):
        with pytest.raises(HTTPException):operation()
    assert not s.query(GeneralLedger).count()
    a[2].account_subtype='PETTY_CASH';s.commit()
    period=s.query(FiscalPeriod).one();period.is_open=False;period.is_closed=True;s.commit()
    with pytest.raises(HTTPException):cashier.post(created['id'],s,ADMIN)
    s.rollback()
    assert not s.query(GeneralLedger).count()


def test_department_scope_applies_to_reads_edit_post_and_balances(db):
    s,u,l,d,a=db
    value=data(db);created=cashier.create(value,s,ADMIN)
    from app.models.department import Department
    from app.models.location_department import LocationDepartment
    other=Department(id=d.id+100,code='OTHER',name='Other department',business_unit_id=u.id)
    s.add(other);s.add(LocationDepartment(location_id=l.id,department_id=other.id));s.commit()
    restricted=SimpleNamespace(id=2,roles=[SimpleNamespace(name='DEPARTMENT',permissions=[SimpleNamespace(code='finance.view')])],default_location_id=l.id,default_department_id=other.id)
    assert cashier.listing(date(2026,1,1),date(2026,1,31),page=1,page_size=100,db=s,user=restricted)['total_items']==0
    with pytest.raises(HTTPException):cashier.detail(created['id'],s,restricted)
    with pytest.raises(HTTPException):cashier.update(created['id'],value,s,restricted)
    with pytest.raises(HTTPException):cashier.post(created['id'],s,restricted)
    # Create cannot escape the assigned department even at the same location.
    with pytest.raises(HTTPException):cashier.create(value,s,restricted)
    with pytest.raises(HTTPException):cashier.listing(date(2026,1,31),date(2026,1,1),page=1,page_size=100,db=s,user=ADMIN)
    assert not s.query(GeneralLedger).count()
    cashier.post(created['id'],s,ADMIN)
    scoped=cash_flow.accounts(date_from=date(2026,1,1),date_to=date(2026,1,31),db=s,user=restricted)
    assert all(x['total_inflow']==0 and x['total_outflow']==0 for x in scoped)
    activity=cash_flow.activity(a[2].id,page=1,page_size=100,db=s,user=restricted)
    assert activity['total_items']==0


def test_void_cannot_be_posted_and_draft_changes_obey_period(db):
    s,u,l,d,a=db
    value=data(db);created=cashier.create(value,s,ADMIN)
    cashier.void(created['id'],s,ADMIN)
    assert s.get(JournalEntry,created['id']).voided_at is not None
    with pytest.raises(HTTPException):cashier.post(created['id'],s,ADMIN)
    with pytest.raises(HTTPException):cashier.update(created['id'],value,s,ADMIN)
    assert not s.query(GeneralLedger).count()


def test_closed_period_blocks_edit_without_changing_draft(db):
    s,u,l,d,a=db
    value=data(db);created=cashier.create(value,s,ADMIN)
    period=s.query(FiscalPeriod).one();period.is_open=False;period.is_closed=True;s.commit()
    with pytest.raises(HTTPException):cashier.update(created['id'],value.model_copy(update={'amount':Decimal(99)}),s,ADMIN)
    s.rollback()
    assert cashier.detail(created['id'],s,ADMIN)['total_debit']==30
    assert not s.query(GeneralLedger).count()


def test_generic_journal_route_cannot_post_unassigned_cashier_for_department_user(db):
    s,u,l,d,a=db
    value=data(db).model_copy(update={'department_id':None})
    created=cashier.create(value,s,ADMIN)
    restricted=SimpleNamespace(id=2,roles=[SimpleNamespace(name='DEPARTMENT')],default_location_id=l.id,default_department_id=d.id)
    with pytest.raises(HTTPException):journals.post_locked_journal(s,journal=s.get(JournalEntry,created['id']),user=restricted)
    assert not s.query(GeneralLedger).count()
