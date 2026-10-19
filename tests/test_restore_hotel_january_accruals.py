"""Accrual restoration is exact, atomic and safe to rerun."""
from datetime import date
from decimal import Decimal as D
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base
from app.models.business_unit import BusinessUnit
from app.models.location import Location
from app.models.chart_of_account import ChartOfAccount
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.fiscal_period import FiscalPeriod
from app.models.general_ledger import GeneralLedger
from scripts import restore_hotel_january_accruals as repair


@pytest.fixture
def db():
    engine=create_engine('sqlite:///:memory:');Base.metadata.create_all(engine)
    db=sessionmaker(bind=engine,expire_on_commit=False)()
    db.add(BusinessUnit(id=1,code='HOTEL',name='Hotel'))
    db.add(Location(id=8,code='H',name='Hotel',business_unit_id=1))
    db.add(FiscalPeriod(fiscal_year=2026,fiscal_month=1,period_name='January',start_date=date(2026,1,1),end_date=date(2026,1,31),is_open=True,is_closed=False,allow_backdated_entries=True))
    accounts={}
    for _,_,lines in repair.EXPECTED.values():
        for code,_,_ in lines:
            if code in accounts:continue
            a=ChartOfAccount(account_number=code,account_name=code,account_type='EXPENSE' if code.startswith('7') else 'LIABILITY',is_active=True,is_posting=True,normal_balance='DEBIT' if code.startswith('7') else 'CREDIT')
            db.add(a);accounts[code]=a
    db.flush()
    for ident,(number,document,lines) in repair.EXPECTED.items():
        j=JournalEntry(id=ident,journal_number=number,document_number=document,posting_date=date(2026,1,31),reference_type='MANUAL',reference_id=ident,status='VOID',location_id=8,business_unit_id=1)
        for n,(code,dr,cr) in enumerate(lines,1):
            j.lines.append(JournalLine(line_number=n,account_id=accounts[code].id,debit=D(dr),credit=D(cr),location_id=8,business_unit_id=1))
        db.add(j)
    db.commit()
    yield db
    db.close();engine.dispose()


def test_restore_original_journals_and_gl_once(db):
    with db.begin():assert repair.restore(db)==3
    assert db.query(GeneralLedger).count()==13
    assert {j.status for j in db.query(JournalEntry).all()}=={'POSTED'}
    db.rollback()
    with db.begin():assert repair.restore(db)==0
    assert db.query(GeneralLedger).count()==13


def test_changed_counterpart_refuses_every_journal(db):
    j=db.get(JournalEntry,1432);j.lines[-1].credit+=1;db.commit()
    with pytest.raises(ValueError,match='full account/debit/credit'):
        with db.begin():repair.restore(db)
    assert db.query(GeneralLedger).count()==0
    assert {j.status for j in db.query(JournalEntry).all()}=={'VOID'}


def test_posting_failure_rolls_back_earlier_journal(db,monkeypatch):
    original=repair.post_locked_journal
    def post(db,*,journal,user):
        if journal.id==1431:raise RuntimeError('Simulated posting failure')
        original(db,journal=journal,user=user)
    monkeypatch.setattr(repair,'post_locked_journal',post)
    with pytest.raises(RuntimeError,match='Simulated'):
        with db.begin():repair.restore(db)
    assert db.query(GeneralLedger).count()==0
    assert {j.status for j in db.query(JournalEntry).all()}=={'VOID'}


def test_closed_period_cannot_be_bypassed(db):
    p=db.query(FiscalPeriod).one();p.is_closed=True;p.is_open=False;db.commit()
    with pytest.raises(HTTPException):
        with db.begin():repair.restore(db)
    assert db.query(GeneralLedger).count()==0
    assert {j.status for j in db.query(JournalEntry).all()}=={'VOID'}
