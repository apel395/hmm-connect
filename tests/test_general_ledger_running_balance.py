"""Regression: GL text/supplier filters must not redefine account balances."""
from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base
from app.models.chart_of_account import ChartOfAccount
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.opening_balance import OpeningBalance
from app.services.general_ledger_report import (
    build_ledger_query,
    ledger_rows_with_balance,
    opening_balances,
)
from app.services.trial_balance_service import TrialBalanceService


def test_document_search_uses_full_account_running_balance_and_matches_trial_balance():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        cash = ChartOfAccount(account_number="100-110-102", account_name="Cash", account_type="ASSET", normal_balance="DEBIT", is_posting=True, is_active=True)
        other = ChartOfAccount(account_number="300-100-001", account_name="Equity", account_type="EQUITY", normal_balance="CREDIT", is_posting=True, is_active=True)
        session.add_all([cash, other])
        session.flush()
        session.add(OpeningBalance(fiscal_year=2026, account_id=cash.id, amount=Decimal("100.00"), balance_type="DEBIT"))
        session.add(OpeningBalance(fiscal_year=2026, account_id=other.id, amount=Decimal("100.00"), balance_type="CREDIT"))
        session.flush()

        for index, value in enumerate((Decimal("50.00"), Decimal("-20.00"), Decimal("30.00")), 1):
            journal = JournalEntry(
                journal_number=f"GL-REG-{index}",
                document_number=f"DOC-{index}",
                posting_date=date(2026, 1, index),
                reference_type="MANUAL",
                reference_id=index,
                status="POSTED",
            )
            journal.lines = [
                JournalLine(account_id=cash.id, debit=max(value, Decimal("0")), credit=max(-value, Decimal("0")), line_number=1),
                JournalLine(account_id=other.id, credit=max(value, Decimal("0")), debit=max(-value, Decimal("0")), line_number=2),
            ]
            session.add(journal)
        session.commit()

        scope = dict(account_id=cash.id, date_from=date(2026, 1, 1), date_to=date(2026, 1, 31))
        full_query = build_ledger_query(session, **scope)
        selected_query = build_ledger_query(session, **scope, search="DOC-2", search_type="DOCUMENT")
        selected_rows = ledger_rows_with_balance(selected_query, balance_query=full_query).all()
        assert len(selected_rows) == 1
        assert selected_rows[0][0].journal_entry.document_number == "DOC-2"
        assert Decimal(selected_rows[0][1]) == Decimal("30.00")

        opening = opening_balances(session, account_id=cash.id, date_from=date(2026, 1, 1))[cash.id]
        assert opening == Decimal("100.00")
        assert opening + Decimal(selected_rows[0][1]) == Decimal("130.00")

        all_rows = ledger_rows_with_balance(full_query).all()
        assert [Decimal(balance) for _, balance in all_rows] == [Decimal("50.00"), Decimal("30.00"), Decimal("60.00")]
        assert Decimal(ledger_rows_with_balance(selected_query, balance_query=full_query).offset(0).limit(1).one()[1]) == Decimal("30.00")
        from app.services.general_ledger_report import ledger_grouped_report
        printed, filtered_debit, filtered_credit = ledger_grouped_report(
            session, **scope, search="DOC-2", search_type="DOCUMENT"
        )
        assert len(printed) == 1
        assert printed[0]["opening_balance"] == Decimal("100.00")
        assert printed[0]["total_debit"] == Decimal("80.00")
        assert printed[0]["total_credit"] == Decimal("20.00")
        assert printed[0]["closing_balance"] == Decimal("160.00")
        assert len(printed[0]["rows"]) == 1
        assert printed[0]["rows"][0]["balance"] == Decimal("130.00")
        assert filtered_debit == Decimal("0.00")
        assert filtered_credit == Decimal("20.00")

        tb = TrialBalanceService(session).report(
            date_from=date(2026, 1, 1),
            date_to=date(2026, 1, 31),
            account_id=cash.id,
            paginate=False,
        )
        assert tb["items"][0]["closing_balance"] == Decimal("160.00")
        assert opening + Decimal(all_rows[-1][1]) == tb["items"][0]["closing_balance"]
    finally:
        session.close()
        engine.dispose()
