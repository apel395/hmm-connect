"""Dana Proyek mapping correction preserves bank/source directions and reconciles net."""
from copy import deepcopy
from datetime import date
from decimal import Decimal as D
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base
from app.models.business_unit import BusinessUnit
from app.models.location import Location
from app.models.department import Department
from app.models.chart_of_account import ChartOfAccount
from app.models.fiscal_period import FiscalPeriod
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.general_ledger import GeneralLedger
from app.models.import_batch import ImportBatch,ImportRow
from app.services.financial_reporting_service import FinancialReportingService
from app.services.profit_loss_delivery import deliver
from scripts import remap_hotel_january_dana_proyek as repair


@pytest.fixture
def db():
    engine=create_engine('sqlite:///:memory:');Base.metadata.create_all(engine)
    db=sessionmaker(bind=engine,expire_on_commit=False)()
    db.add(BusinessUnit(id=1,code='HOTEL',name='Hotel'));db.add(Location(id=8,code='H',name='Hotel',business_unit_id=1))
    db.add(Department(id=16,code='BOD',name='Board of Directur',business_unit_id=1))
    db.add(FiscalPeriod(fiscal_year=2026,fiscal_month=1,period_name='January',start_date=date(2026,1,1),end_date=date(2026,1,31),is_open=True,is_closed=False,allow_backdated_entries=True))
    accounts={}
    for code,kind in [(repair.OLD,'ASSET'),(repair.NEW,'EXPENSE'),(repair.BANK,'ASSET'),('400-100-100','REVENUE')]:
        a=ChartOfAccount(account_number=code,account_name=code,account_type=kind,is_active=True,is_posting=True,normal_balance='CREDIT' if kind=='REVENUE' else 'DEBIT',financial_statement_group='OPERATING_REVENUE' if kind=='REVENUE' else 'OPERATING_EXPENSE' if kind=='EXPENSE' else 'CURRENT_ASSET')
        db.add(a);accounts[code]=a
    db.add(ImportBatch(id=1,batch_number='JAN',source='ACCOUNTING_IMPORT',batch_name='January',import_type='JOURNAL',status='IMPORTED'));db.flush()
    for ident,(number,register,posting_date,manifest) in repair.JOURNALS.items():
        j=JournalEntry(id=ident,journal_number=number,external_reference='HOTEL-JAN2026-REG-'+register,posting_date=posting_date,status='DRAFT',reference_type='MANUAL',reference_id=0,source_type='JOURNAL_IMPORT',import_batch_id=1,location_id=8,business_unit_id=1)
        for n,(source_row,code,dr,cr) in enumerate(manifest,1):
            dept=16 if code==repair.OLD else None
            j.lines.append(JournalLine(line_number=n,account_id=accounts[code].id,debit=D(dr),credit=D(cr),description='DANA PROYEK',location_id=8,business_unit_id=1,department_id=dept))
            normalized=dict(account_id=accounts[code].id,account_code=code,legacy_code='591007' if code==repair.OLD else '102025',debit=dr,credit=cr,department_id=dept,business_unit_id=1,location_id=8)
            raw={**normalized,'register':register,'source_sha256':repair.SOURCE_HASH,'description':'DANA PROYEK'}
            db.add(ImportRow(id=source_row,import_batch_id=1,row_number=source_row,document_type='JOURNAL',entity_type='JOURNAL_ENTRY',entity_id=ident,status='IMPORTED',raw_data_json=raw,normalized_data_json=normalized))
        db.add(j);db.flush()
        repair.post_locked_journal(db,journal=j,user=SimpleNamespace(id=None,full_name='Fixture',roles=[]))
    baseline=JournalEntry(journal_number='BASE',posting_date=date(2026,1,31),status='POSTED',reference_type='MANUAL',reference_id=0,location_id=8,business_unit_id=1)
    baseline.lines=[JournalLine(account_id=accounts['400-100-100'].id,debit=0,credit=D('69292329.66'),location_id=8,business_unit_id=1),JournalLine(account_id=accounts[repair.BANK].id,debit=D('69292329.66'),credit=0,location_id=8,business_unit_id=1)]
    db.add(baseline);db.commit()
    yield db
    db.close();engine.dispose()


def test_mapping_reposts_both_journals_and_preserves_sources_and_bank(db):
    raw={r.id:deepcopy(r.raw_data_json) for r in db.query(ImportRow)}
    original_bank=[(l.id,l.debit,l.credit) for l in db.query(JournalLine).join(ChartOfAccount).filter(ChartOfAccount.account_number==repair.BANK).order_by(JournalLine.id)]
    db.rollback()
    with db.begin():result=repair.remap(db)
    assert result['journals_changed']==2 and result['lines_changed']==5
    assert result['NOP_before']=='69292329.66'
    assert result['NOP_after']=='90452177.66'
    assert result['NOP_change']=='21159848.00'
    assert db.query(GeneralLedger).count()==10
    assert {r.id:r.raw_data_json for r in db.query(ImportRow)}==raw
    assert [(l.id,l.debit,l.credit) for l in db.query(JournalLine).join(ChartOfAccount).filter(ChartOfAccount.account_number==repair.BANK).order_by(JournalLine.id)]==original_bank
    report=deliver(FinancialReportingService(db),as_of_date=date(2026,1,31),report_scope='HOTEL')
    assert next(r for r in report['presentation_rows'] if r['key']=='NOP')['periods']['YTD']['current']==D('90452177.66')
    assert sum(a['periods']['YTD']['current'] for a in report['related_accounts'] if '591007' in a.get('legacy_codes',[]))==D('-21159848')
    for r in db.query(ImportRow):
        if r.raw_data_json['legacy_code']=='591007':
            assert r.normalized_data_json['account_code']==repair.NEW
            assert r.normalized_data_json['original_account_id']==raw[r.id]['account_id']
    db.rollback()
    with db.begin():assert repair.remap(db)['journals_changed']==0
    assert db.query(GeneralLedger).count()==10


@pytest.mark.parametrize('fault',['source','gl','closed_period'])
def test_unverified_or_locked_entry_refuses_without_reclassification(db,fault):
    if fault=='source':
        row=db.query(ImportRow).first();data=dict(row.raw_data_json);data['source_sha256']='wrong';row.raw_data_json=data
    elif fault=='gl':db.query(GeneralLedger).first().debit+=1
    else:
        period=db.query(FiscalPeriod).one();period.is_open=False;period.is_closed=True
    db.commit()
    original=[(l.id,l.account_id,l.debit,l.credit) for l in db.query(JournalLine).order_by(JournalLine.id)];db.rollback()
    with pytest.raises((ValueError,HTTPException)):
        with db.begin():repair.remap(db)
    assert [(l.id,l.account_id,l.debit,l.credit) for l in db.query(JournalLine).order_by(JournalLine.id)]==original
    assert {j.status for j in db.query(JournalEntry)}=={'POSTED'}


def test_failure_after_first_journal_rolls_back_both_mappings_and_gl(db,monkeypatch):
    old=repair.post_locked_journal
    def post(db,*,journal,user):
        if journal.id==4660:raise RuntimeError('Simulated posting failure')
        old(db,journal=journal,user=user)
    monkeypatch.setattr(repair,'post_locked_journal',post)
    before=[(g.id,g.account_id,g.debit,g.credit) for g in db.query(GeneralLedger).order_by(GeneralLedger.id)];db.rollback()
    with pytest.raises(RuntimeError,match='Simulated'):
        with db.begin():repair.remap(db)
    assert [(g.id,g.account_id,g.debit,g.credit) for g in db.query(GeneralLedger).order_by(GeneralLedger.id)]==before
    assert all(r.normalized_data_json['account_code']==repair.OLD for r in db.query(ImportRow) if r.raw_data_json['legacy_code']=='591007')
