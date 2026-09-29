from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.chart_of_account import ChartOfAccount
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.services.trial_balance_service import TrialBalanceService


def test_trial_balance_reports_unbalanced_opening_even_when_account_search_filters_rows():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        asset = ChartOfAccount(
            account_number="100-TEST", account_name="Asset Test",
            account_type="ASSET", normal_balance="DEBIT",
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
        assert report["summary"]["is_balanced"] is False
    finally:
        db.close()
        engine.dispose()
