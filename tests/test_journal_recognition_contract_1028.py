from datetime import date
from decimal import Decimal
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.api.v1 import journals
from app.models.fiscal_period import FiscalPeriod
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.general_ledger import GeneralLedger
from app.models.opening_balance import OpeningBalance
from app.services.general_ledger_report import build_ledger_query, ledger_totals
from app.services.journal_recognition import recognized_journal_filter
from app.services.trial_balance_service import TrialBalanceService
from app.services.financial_statement_service import FinancialStatementService
from app.services.financial_reporting_service import FinancialReportingService
from app.services.financial_reconciliation_service import FinancialReconciliationService
from app.services.cash_flow_service import CashFlowService
from app.services.period_closing_service import PeriodClosingService
from test_financial_reporting_closing import db, activity, USER

ADMIN=SimpleNamespace(id=1,roles=[SimpleNamespace(name='SYSTEM_ADMINISTRATOR')],location_id=None,default_location_id=None)


def debit(session):
    return sum((i['period_debit'] for i in TrialBalanceService(session).report(date_from=date(2026,1,1),date_to=date(2026,1,31))['items']),Decimal(0))


def test_all_accounting_reads_share_balanced_draft_and_ignore_gl_cache(db):
    session,a=db;a[2].account_subtype='CASH';session.commit()
    entry=activity(session,a,date(2026,1,10),'100','30',status='DRAFT')
    assert debit(session)==100
    assert ledger_totals(build_ledger_query(session,date_from=date(2026,1,1),date_to=date(2026,1,31)))==(100,100)
    assert FinancialStatementService(session).profit_and_loss(date_from=date(2026,1,1),date_to=date(2026,1,31))['summary']['net_profit_after_tax']==70
    assert FinancialReportingService(session).build(report_type='PROFIT_LOSS',as_of_date=date(2026,1,31))['section_totals']['REVENUE']['MTD']['current']==100
    assert CashFlowService(session).summary(date_from=date(2026,1,1),date_to=date(2026,1,31))['net_cash_flow']==70
    assert FinancialReconciliationService(session)._gl_balance([a[2].id],None,None)==70
    # A cache row must never be unioned into canonical journal-line reporting.
    session.add(GeneralLedger(journal_number='GL-OLD-CACHE',posting_date=entry.posting_date,fiscal_year=2026,fiscal_period=1,account_id=a[2].id,debit=70,credit=0,reference_type='MANUAL',reference_id=entry.id,reference_number=entry.journal_number));session.commit()
    assert debit(session)==100 and ledger_totals(build_ledger_query(session))==(100,100)
    entry.status='POSTED';session.commit()
    assert debit(session)==100


@pytest.mark.parametrize('issue',['unbalanced','zero_line','both_sides','inactive_account','statistic','location','dimensions','closed'])
def test_incomplete_drafts_do_not_contribute(db,issue):
    session,a=db;entry=activity(session,a,date(2026,1,10),'100','30',status='DRAFT')
    if issue=='unbalanced':entry.lines[2].debit=1
    elif issue=='zero_line':entry.lines.append(JournalLine(account_id=a[2].id,debit=0,credit=0))
    elif issue=='both_sides':entry.lines[0].debit=10;entry.lines[0].credit=110;entry.lines[2].debit=80
    elif issue=='inactive_account':a[0].is_active=False
    elif issue=='statistic':a[0].account_type='STATISTIC'
    elif issue=='location':entry.location_id=None
    elif issue=='dimensions':entry.lines[0].location_id=99
    else:session.get(FiscalPeriod,1).is_open=False;session.get(FiscalPeriod,1).is_closed=True
    session.commit()
    assert not session.query(JournalEntry.id).filter(recognized_journal_filter()).all()
    assert debit(session)==0 and ledger_totals(build_ledger_query(session))==(0,0)


def test_edit_draft_recognized_values_then_post_once(db,monkeypatch):
    from app.schemas.journal import JournalUpdate
    session,a=db;entry=activity(session,a,date(2026,1,10),'100','30',status='DRAFT')
    monkeypatch.setattr(journals,'record_audit',lambda *args,**kw:None)
    # Existing fixture dimensions are intentionally minimal; this test changes only description first.
    journals.update(entry.id,JournalUpdate(description='Reviewed by Finance'),session,ADMIN)
    entry.lines[0].credit=200;entry.lines[2].debit=170;session.commit()
    assert debit(session)==200 and not session.query(GeneralLedger).count()
    journals.post(entry.id,session,ADMIN)
    assert entry.status=='POSTED' and debit(session)==200 and session.query(GeneralLedger).count()==3
    with pytest.raises(HTTPException):journals.post(entry.id,session,ADMIN)
    assert session.query(GeneralLedger).count()==3


def test_closed_period_actions_and_reopen_keep_posted_identity(db,monkeypatch):
    from app.schemas.journal import JournalUpdate
    session,a=db;entry=activity(session,a,date(2026,1,10),'100','30',status='DRAFT')
    monkeypatch.setattr(journals,'record_audit',lambda *args,**kw:None);monkeypatch.setattr('app.services.period_closing_service.record_audit',lambda *args,**kw:None)
    before_openings=session.query(OpeningBalance).count()
    PeriodClosingService.close(session,1,ADMIN);session.commit();cache_count=session.query(GeneralLedger).count()
    assert entry.status=='POSTED';view=journals.serialize(entry,ADMIN)
    assert view['period_locked'] and not view['allowed_actions']['can_unpost']
    for action in (lambda:journals.update(entry.id,JournalUpdate(description='Blocked'),session,ADMIN),lambda:journals.unpost(entry.id,session,ADMIN)):
        with pytest.raises(HTTPException):action()
        session.rollback()
    PeriodClosingService.reopen(session,1,ADMIN,'Finance correction');session.commit()
    assert entry.status=='POSTED' and journals.serialize(entry,ADMIN)['allowed_actions']['can_unpost']
    journals.unpost(entry.id,session,ADMIN)
    assert entry.status=='DRAFT' and debit(session)==100
    PeriodClosingService.close(session,1,ADMIN);session.commit()
    assert entry.status=='POSTED' and session.query(OpeningBalance).count()==before_openings
    assert session.query(GeneralLedger).count()==cache_count


def test_close_failure_rolls_back_earlier_finalization_without_caller_rollback(db,monkeypatch):
    session,a=db;first=activity(session,a,date(2026,1,10),'100','30',status='DRAFT');second=activity(session,a,date(2026,1,11),'100','30',status='DRAFT')
    real=journals.post_locked_journal
    monkeypatch.setattr(journals,'record_audit',lambda *args,**kw:None)
    def fail_later(db,*,journal,**kw):
        if journal.id==second.id:raise HTTPException(409,'Simulated source dependency')
        return real(db,journal=journal,**kw)
    monkeypatch.setattr(journals,'post_locked_journal',fail_later)
    with pytest.raises(HTTPException):PeriodClosingService.close(session,1,ADMIN)
    assert first.status==second.status=='DRAFT'
    assert not session.query(GeneralLedger).count() and session.get(FiscalPeriod,1).is_open


def test_manual_blank_source_type_is_included_consistently(db):
    session,a=db;a[2].account_subtype='CASH'
    entry=activity(session,a,date(2026,1,10),'100','30',status='DRAFT')
    entry.reference_type="";session.commit()
    assert debit(session)==100
    assert ledger_totals(build_ledger_query(session))==(100,100)
    assert CashFlowService(session).summary(date_from=date(2026,1,1),date_to=date(2026,1,31))['net_cash_flow']==70
    assert FinancialReportingService(session).build(report_type='PROFIT_LOSS',as_of_date=date(2026,1,31))['section_totals']['REVENUE']['MTD']['current']==100


@pytest.mark.parametrize('role',['FINANCE','COST_CONTROL'])
def test_journal_management_uses_persisted_permission_for_finance_and_cost_control(db,role):
    session,a=db;entry=activity(session,a,date(2026,1,10),'100','30',status='DRAFT')
    actor=SimpleNamespace(id=1,roles=[SimpleNamespace(name=role,permissions=[SimpleNamespace(code='journal.manage')])])
    assert journals.journal_manage_user(actor) is actor
    assert journals.serialize(entry,actor)['allowed_actions']['can_edit']
    actor.roles[0].permissions=[SimpleNamespace(code='journal.view')]
    with pytest.raises(HTTPException) as error:journals.journal_manage_user(actor)
    assert error.value.status_code==403
    assert not journals.serialize(entry,actor)['allowed_actions']['can_edit']


def test_location_reports_inherit_absent_line_dimensions_from_header(db):
    session,a=db;entry=activity(session,a,date(2026,1,10),'100','30',status='DRAFT')
    for line in entry.lines:line.location_id=None;line.business_unit_id=None
    session.commit()
    assert FinancialReconciliationService(session)._gl_balance([a[2].id],1,None)==70
    assert ledger_totals(build_ledger_query(session,location_id=1))==(100,100)
    report=TrialBalanceService(session).report(date_from=date(2026,1,1),date_to=date(2026,1,31),location_id=1)
    assert sum(row['period_debit'] for row in report['items'])==100
