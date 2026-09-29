from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.chart_of_account import ChartOfAccount
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.opening_balance import OpeningBalance
from app.services import opening_balance_service as module


USER = SimpleNamespace(
    id=1, roles=[SimpleNamespace(name="SYSTEM_ADMINISTRATOR")],
    location_id=None, default_location_id=None,
)


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    monkeypatch.setattr(module, "record_audit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module.JournalService.post.__func__.__globals__["FiscalPeriodService"], "validate_posting_date", lambda **_kwargs: None)
    monkeypatch.setattr(module, "next_document_number", lambda *_args, **_kwargs: "OPEN-ADJ-TEST")
    posted = []
    monkeypatch.setattr(module.GeneralLedgerService, "post", lambda **kwargs: posted.append(kwargs))
    session.test_ledger_posts = posted
    yield session
    session.close()
    engine.dispose()


def seed(db):
    asset = ChartOfAccount(
        account_number="100-TEST", account_name="Asset",
        account_type="ASSET", normal_balance="DEBIT",
        is_active=True, is_posting=True,
    )
    liability = ChartOfAccount(
        account_number="200-TEST", account_name="Verified liability",
        account_type="LIABILITY", normal_balance="CREDIT",
        is_active=True, is_posting=True,
    )
    db.add_all([asset, liability])
    db.flush()
    journal = JournalEntry(
        journal_number="OPEN-TEST", posting_date=date(2026, 1, 1),
        status="POSTED", reference_type="OPENING_BALANCE", reference_id=2026,
        document_type="OPENING_BALANCE", document_number="OPEN-TEST", location_id=1,
    )
    journal.lines = [JournalLine(
        account_id=asset.id, debit=Decimal("125.00"), credit=Decimal("0.00"),
    )]
    db.add(journal)
    db.flush()
    db.add(OpeningBalance(
        fiscal_year=2026, account_id=asset.id,
        amount=Decimal("125.00"), balance_type="DEBIT",
        journal_entry_id=journal.id,
    ))
    db.commit()
    return journal.id, liability.id


def test_manual_adjustment_keeps_original_and_posts_only_chosen_line(db):
    journal_id, liability_id = seed(db)
    result = module.OpeningBalanceService(db).post_adjustment(
        user=USER, journal_id=journal_id,
        lines=[{"account_id": liability_id, "amount": "125.00", "balance_type": "CREDIT"}],
        description="Verified opening liability",
    )
    original = db.get(JournalEntry, journal_id)
    adjustment = db.get(JournalEntry, result["journal_id"])
    assert original.status == "POSTED"
    assert len(original.lines) == 1
    assert original.lines[0].debit == Decimal("125.00")
    assert adjustment.id != original.id
    assert adjustment.reference_type == "OPENING_BALANCE_ADJUSTMENT"
    assert adjustment.reference_id == original.id
    assert len(adjustment.lines) == 1
    assert adjustment.lines[0].account_id == liability_id
    assert adjustment.lines[0].credit == Decimal("125.00")
    assert db.query(OpeningBalance).filter(OpeningBalance.journal_entry_id == journal_id).count() == 1
    assert len(db.test_ledger_posts) == 1


def test_partial_adjustment_is_recorded_without_system_completion(db):
    journal_id, liability_id = seed(db)
    result = module.OpeningBalanceService(db).post_adjustment(
        user=USER, journal_id=journal_id,
        lines=[{"account_id": liability_id, "amount": "124.00", "balance_type": "CREDIT"}],
        description="Confirmed portion only",
    )
    assert result["adjustment_difference"] == Decimal("-124.00")
    assert db.query(JournalLine).filter(JournalLine.journal_entry_id == journal_id).count() == 1


def test_adjustment_requires_reason(db):
    journal_id, liability_id = seed(db)
    with pytest.raises(HTTPException) as error:
        module.OpeningBalanceService(db).post_adjustment(
            user=USER, journal_id=journal_id,
            lines=[{"account_id": liability_id, "amount": "125.00", "balance_type": "CREDIT"}],
            description=None,
        )
    assert error.value.status_code == 400
    assert db.query(JournalEntry).count() == 1
