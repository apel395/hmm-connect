from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.chart_of_account import ChartOfAccount
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.opening_balance import OpeningBalance
from app.services.trial_balance_service import TrialBalanceService
from app.services.general_ledger_report import opening_balances, ledger_grouped_report
from app.services.cash_flow_service import CashFlowService


def test_trial_balance_reports_unbalanced_opening_even_when_account_search_filters_rows():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        asset = ChartOfAccount(
            account_number="100-TEST", account_name="Asset Test",
            account_type="ASSET", account_subtype="CASH", normal_balance="DEBIT",
            is_active=True, is_posting=True,
        )
        other = ChartOfAccount(
            account_number="300-TEST", account_name="Equity Test",
            account_type="EQUITY", normal_balance="CREDIT",
            is_active=True, is_posting=True,
        )
        db.add_all([asset, other])
        db.flush()
        journal = JournalEntry(
            journal_number="OPEN-TEST", posting_date=date(2026, 1, 1),
            status="POSTED", reference_type="OPENING_BALANCE", reference_id=2026,
        )
        journal.lines = [
            JournalLine(account_id=asset.id, debit=Decimal("125.00"), credit=Decimal("0.00")),
        ]
        db.add(journal)
        db.add(OpeningBalance(
            fiscal_year=2026, account_id=asset.id, amount=Decimal("125.00"),
            balance_type="DEBIT", journal_entry=journal,
        ))
        activity = JournalEntry(
            journal_number="MAN-TEST", posting_date=date(2026, 9, 5),
            status="POSTED", reference_type="MANUAL", reference_id=1,
        )
        activity.lines = [
            JournalLine(account_id=asset.id, debit=Decimal("0.00"), credit=Decimal("10.00")),
            JournalLine(account_id=other.id, debit=Decimal("10.00"), credit=Decimal("0.00")),
        ]
        db.add(activity)
        db.commit()

        report = TrialBalanceService(db).report(
            date_from=date(2026, 9, 1),
            date_to=date(2026, 9, 30),
            search="Asset Test",
        )
        assert len(report["items"]) == 1
        assert report["summary"]["opening_debit"] == Decimal("125.00")
        assert report["summary"]["opening_credit"] == Decimal("0.00")
        assert report["summary"]["opening_difference"] == Decimal("125.00")
        assert report["summary"]["closing_difference"] == Decimal("125.00")
        assert report["items"][0]["opening_balance"] == Decimal("125.00")
        assert report["items"][0]["closing_balance"] == Decimal("115.00")
        assert report["items"][0]["opening_debit"] == Decimal("125.00")
        assert report["items"][0]["opening_credit"] == Decimal("0.00")
        assert report["items"][0]["closing_debit"] == Decimal("115.00")
        assert report["items"][0]["closing_credit"] == Decimal("0.00")
        assert report["summary"]["is_balanced"] is False
        assert opening_balances(db, account_id=asset.id, date_from=date(2026, 9, 1))[asset.id] == Decimal("125.00")
        accounts, debit, credit = ledger_grouped_report(
            db, account_id=asset.id, date_from=date(2026, 9, 1),
            date_to=date(2026, 9, 30),
        )
        assert len(accounts) == 1
        assert accounts[0]["opening_balance"] == Decimal("125.00")
        assert accounts[0]["closing_balance"] == Decimal("115.00")
        assert credit == Decimal("10.00")
        assert CashFlowService(db).opening(date(2026, 9, 1), asset.id) == Decimal("125.00")
    finally:
        db.close()
        engine.dispose()


def test_trial_balance_keeps_annual_snapshot_and_separates_prior_from_selected_movement():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        asset = ChartOfAccount(
            account_number="100-YTD", account_name="Annual Asset",
            account_type="ASSET", normal_balance="DEBIT",
            is_active=True, is_posting=True,
        )
        equity = ChartOfAccount(
            account_number="300-YTD", account_name="Annual Equity",
            account_type="EQUITY", normal_balance="CREDIT",
            is_active=True, is_posting=True,
        )
        db.add_all([asset, equity])
        db.flush()
        db.add_all([
            OpeningBalance(fiscal_year=2025, account_id=asset.id, amount=Decimal("999.00"), balance_type="DEBIT"),
            OpeningBalance(fiscal_year=2026, account_id=asset.id, amount=Decimal("100.00"), balance_type="DEBIT"),
        ])
        for number, day, amount in (
            ("PRIOR", date(2025, 12, 31), "50.00"),
            ("JAN", date(2026, 1, 10), "10.00"),
            ("SEP", date(2026, 9, 5), "5.00"),
        ):
            entry = JournalEntry(
                journal_number=number, posting_date=day, status="POSTED",
                reference_type="MANUAL", reference_id=1,
            )
            entry.lines = [
                JournalLine(account_id=asset.id, debit=Decimal(amount), credit=Decimal("0")),
                JournalLine(account_id=equity.id, debit=Decimal("0"), credit=Decimal(amount)),
            ]
            db.add(entry)
        db.commit()
        report = TrialBalanceService(db).report(
            date_from=date(2026, 9, 1), date_to=date(2026, 9, 30),
            account_id=asset.id,
        )
        row = report["items"][0]
        assert report["opening_as_of"] == date(2025, 12, 31)
        assert report["movement_from"] == date(2026, 9, 1)
        assert row["opening_debit"] == Decimal("100.00")
        assert row["prior_debit"] == Decimal("10.00")
        assert row["period_debit"] == Decimal("5.00")
        assert row["closing_debit"] == Decimal("115.00")
        assert report["summary"]["opening_debit"] == Decimal("100.00")
        assert report["summary"]["prior_debit"] == Decimal("10.00")
        assert report["summary"]["period_debit"] == Decimal("5.00")
    finally:
        db.close()
        engine.dispose()
