from decimal import Decimal

import pytest
from types import SimpleNamespace
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.chart_of_account import ChartOfAccount
from app.models.opening_balance import OpeningBalance
from app.models.journal_entry import JournalEntry
from app.services import opening_balance_service as module
from app.services.opening_balance_service import OpeningBalanceService


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()
    engine.dispose()


def account(db, code, account_type, normal_balance):
    row = ChartOfAccount(
        account_number=code,
        account_name=code,
        account_type=account_type,
        normal_balance=normal_balance,
        is_active=True,
        is_posting=True,
    )
    db.add(row)
    db.flush()
    return row


def test_opening_preview_shows_unbalanced_input_without_generated_equity(db):
    asset = account(db, "100-TEST", "ASSET", "DEBIT")
    equity = account(db, "300-TEST", "EQUITY", "CREDIT")
    preview = OpeningBalanceService(db).prepare(
        fiscal_year=2026,
        lines=[{"account_id": asset.id, "amount": "125.00", "balance_type": "DEBIT"}],
    )
    assert preview["lines"] == [{
        "account_id": asset.id,
        "account_code": asset.account_number,
        "balance_type": "DEBIT",
        "amount": Decimal("125.00"),
    }]
    assert preview["total_debit"] == Decimal("125.00")
    assert preview["total_credit"] == Decimal("0.00")
    assert preview["difference"] == Decimal("125.00")
    assert preview["differences_ok"] is False
    assert equity.id not in [line["account_id"] for line in preview["lines"]]


def test_opening_post_keeps_user_entered_imbalance_without_journal(db, monkeypatch):
    asset = account(db, "100-TEST", "ASSET", "DEBIT")
    monkeypatch.setattr(module, "resolve_location_id", lambda *_args: 1)
    monkeypatch.setattr(module, "record_audit", lambda *_args, **_kwargs: None)
    result = OpeningBalanceService(db).post(
        user=SimpleNamespace(id=1), fiscal_year=2026, location_id=1,
        lines=[{"account_id": asset.id, "amount": "125.00", "balance_type": "DEBIT"}],
        description="Opening figures verified",
    )
    assert result["difference"] == Decimal("125.00")
    assert result["total_credit"] == Decimal("0.00")
    row = db.query(OpeningBalance).one()
    assert row.amount == Decimal("125.00")
    assert row.balance_type == "DEBIT"
    assert row.journal_entry_id is None
    assert db.query(JournalEntry).count() == 0


def test_opening_preview_accepts_manually_entered_equity(db):
    asset = account(db, "100-TEST", "ASSET", "DEBIT")
    equity = account(db, "300-TEST", "EQUITY", "CREDIT")
    preview = OpeningBalanceService(db).prepare(
        fiscal_year=2026,
        lines=[
            {"account_id": asset.id, "amount": "125.00", "balance_type": "DEBIT"},
            {"account_id": equity.id, "amount": "125.00", "balance_type": "CREDIT"},
        ],
    )
    assert preview["differences_ok"] is True
    assert preview["difference"] == Decimal("0.00")
    assert len(preview["lines"]) == 2
    assert all("contra" not in line for line in preview["lines"])
