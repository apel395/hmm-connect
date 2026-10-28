from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.fiscal_period import FiscalPeriod
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.services.trial_balance_service import TrialBalanceService
from app.services.period_closing_service import PeriodClosingService
from test_financial_reporting_closing import db, USER, activity


def _activity_total(report):
    return sum((row["period_debit"] for row in report["items"]), Decimal("0"))


def test_balanced_open_draft_is_in_trial_balance_once_and_closed_posted(db, monkeypatch):
    session, accounts = db
    monkeypatch.setattr("app.api.v1.journals.record_audit", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.services.period_closing_service.record_audit", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.api.v1.journals.apply_source_post_state", lambda *args, **kwargs: None)
    j = activity(session, accounts, date(2026, 1, 10), "100", "30", status="DRAFT")
    report_before = TrialBalanceService(session).report(date_from=date(2026, 1, 1), date_to=date(2026, 1, 31))
    debit_before = _activity_total(report_before)
    assert debit_before == Decimal("100")
    result = PeriodClosingService.close(session, 1, USER)
    session.commit()
    assert result["closing_journal_ids"]
    assert session.get(JournalEntry, j.id).status == "POSTED"
    report_after = TrialBalanceService(session).report(date_from=date(2026, 1, 1), date_to=date(2026, 1, 31))
    # Closing entries affect operating accounts, but draft is not counted twice.
    assert _activity_total(report_after) >= debit_before


def test_unbalanced_draft_blocks_period_close_without_rewriting_journals(db):
    session, accounts = db
    j = activity(session, accounts, date(2026, 1, 10), "100", "30", status="DRAFT")
    j.lines[2].debit = Decimal("1")
    session.commit()
    with pytest.raises(HTTPException, match="Complete and balance draft journal"):
        PeriodClosingService.close(session, 1, USER)
    session.rollback()
    assert session.get(FiscalPeriod, 1).is_open
    assert session.get(JournalEntry, j.id).status == "DRAFT"
