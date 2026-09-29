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
    monkeypatch.setattr(module.FiscalPeriodService, "validate_posting_date", lambda **_kwargs: None)
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
        document_type="OPENING_BALANCE", document_number="OPEN-TEST",
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


def test_exact_manual_completion_adds_only_chosen_account(db):
    journal_id, liability_id = seed(db)
    result = module.OpeningBalanceService(db).complete_imbalance(
        user=USER, journal_id=journal_id,
        lines=[{"account_id": liability_id, "amount": "125.00", "balance_type": "CREDIT"}],
        description="Verified opening liability",
    )
    assert result["difference"] == Decimal("0.00")
    journal = db.get(JournalEntry, journal_id)
    assert journal.status == "POSTED"
    assert sum((line.debit - line.credit for line in journal.lines), Decimal("0")) == 0
    assert db.query(OpeningBalance).filter(OpeningBalance.journal_entry_id == journal_id).count() == 2
    assert len(db.test_ledger_posts) == 1
    assert db.test_ledger_posts[0]["account_id"] == liability_id
    with pytest.raises(HTTPException) as error:
        module.OpeningBalanceService(db).complete_imbalance(
            user=USER, journal_id=journal_id,
            lines=[{"account_id": liability_id, "amount": "125.00", "balance_type": "CREDIT"}],
            description=None,
        )
    assert error.value.status_code == 409


def test_partial_completion_is_rejected_without_writes(db):
    journal_id, liability_id = seed(db)
    with pytest.raises(HTTPException) as error:
        module.OpeningBalanceService(db).complete_imbalance(
            user=USER, journal_id=journal_id,
            lines=[{"account_id": liability_id, "amount": "124.00", "balance_type": "CREDIT"}],
            description=None,
        )
    assert error.value.status_code == 400
    assert db.query(JournalLine).filter(JournalLine.journal_entry_id == journal_id).count() == 1
    assert len(db.test_ledger_posts) == 0
