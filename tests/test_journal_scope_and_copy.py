from datetime import date
from decimal import Decimal
from types import SimpleNamespace
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
from app.models.general_ledger import GeneralLedger
from app.schemas.journal import JournalCreate
from app.api.v1 import journals

ADMIN = SimpleNamespace(id=1, roles=[SimpleNamespace(name="SYSTEM_ADMINISTRATOR")], default_location_id=None, location_id=None)

@pytest.fixture
def data(monkeypatch):
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    monkeypatch.setattr(journals, 'record_audit', lambda *a, **k: None)
    monkeypatch.setattr(journals, 'next_document_number', lambda *a, **k: 'MAN-COPY-1')
    hotel, project = BusinessUnit(code='HTL',name='Hotel'), BusinessUnit(code='PRJ',name='Project Catering')
    db.add_all([hotel,project]); db.flush()
    hloc, ploc = Location(code='H',name='Hotel',business_unit_id=hotel.id), Location(code='P',name='Rumin',business_unit_id=project.id)
    account = ChartOfAccount(account_number='700-500-119',account_name='Supplies',account_type='EXPENSE',normal_balance='DEBIT',is_active=True,is_posting=True)
    db.add_all([hloc,ploc,account]);db.flush()
    for number, location, unit in [('HTL',hloc,None),('PRJ',ploc,project.id)]:
        j = JournalEntry(journal_number=number,posting_date=date(2026,10,1),status='POSTED',reference_type='GOODS_RECEIPT',reference_id=50,location_id=location.id,business_unit_id=unit,document_number='GR-TEST')
        j.lines=[JournalLine(account_id=account.id,debit=100,credit=0,location_id=location.id,business_unit_id=unit)]
        db.add(j)
    db.commit()
    yield db,hotel,project,hloc,ploc
    db.close();engine.dispose()

def listing(db,user,unit=None):
    return journals.listing(page=1,page_size=100,search=None,status=None,date_from=None,date_to=None,reference_type=None,account_id=None,supplier_id=None,location_id=None,business_unit_id=unit,db=db,user=user)

def test_unit_filter_includes_legacy_null_header_and_totals(data):
    db,hotel,project,*_=data
    result=listing(db,ADMIN,hotel.id)
    assert [j['journal_number'] for j in result['items']]==['HTL']
    assert result['summary']['total_debit']==Decimal('100')
    assert [j['journal_number'] for j in listing(db,ADMIN,project.id)['items']]==['PRJ']

def test_assigned_user_scope_cannot_read_or_copy_other_location(data):
    db,hotel,project,hloc,ploc=data
    user=SimpleNamespace(id=2,roles=[],default_location_id=hloc.id,location_id=hloc.id)
    scope=journals.journal_scope(db=db,user=user)
    assert scope['location_locked'] and scope['default_business_unit_id']==hotel.id
    assert [l['id'] for l in scope['locations']]==[hloc.id]
    assert [r['journal_number'] for r in listing(db,user)['items']]==['HTL']
    other=db.query(JournalEntry).filter_by(journal_number='PRJ').one()
    with pytest.raises(HTTPException) as error:
        journals.copy_template(other.id,db=db,user=user)
    assert error.value.status_code==404

def test_copy_template_is_read_only_and_save_is_independent_manual_draft(data):
    db,hotel,project,hloc,ploc=data
    original=db.query(JournalEntry).filter_by(journal_number='PRJ').one()
    original.reference_type='MANUAL'
    original.reference_id=0
    db.commit()
    before=db.query(JournalEntry).count()
    template=journals.copy_template(original.id,db=db,user=ADMIN)
    assert db.query(JournalEntry).count()==before
    payload=JournalCreate(copied_from_journal_id=original.id,posting_date=date(2026,10,10),business_unit_id=project.id,location_id=ploc.id,
        document_type='MANUAL_JOURNAL',document_number='MY-COPY',reference_type='MANUAL',reference_id=0,lines=template['lines'])
    saved=journals.create(payload,db=db,user=ADMIN)
    assert saved['status']=='DRAFT' and saved['reference_type']=='MANUAL' and saved['reference_id']==0
    assert saved['reference_number']=='MY-COPY'
    assert db.query(GeneralLedger).count()==0
    assert original.status=='POSTED' and original.reference_type=='MANUAL'

def test_opening_and_closing_journals_cannot_be_copied(data):
    db,*_=data
    original=db.query(JournalEntry).first()
    for source in ['OPENING_BALANCE','PERIOD_CLOSE','YEAR_END','GOODS_RECEIPT','SUPPLIER_INVOICE','SUPPLIER_PAYMENT','AMORTIZATION','FIXED_ASSET_DEPRECIATION']:
        original.reference_type=source
        with pytest.raises(HTTPException) as error:
            journals.copy_template(original.id,db=db,user=ADMIN)
        assert error.value.status_code==409
