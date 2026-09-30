from datetime import date
from decimal import Decimal

from fastapi import HTTPException

import pytest
from types import SimpleNamespace
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.chart_of_account import ChartOfAccount
from app.models.opening_balance import OpeningBalance
from app.models.fiscal_period import FiscalPeriod
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


def open_year(db, fiscal_year=2026):
    period = FiscalPeriod(
        fiscal_year=fiscal_year, fiscal_month=9, period_name="September 2026",
        start_date=date(fiscal_year, 9, 1), end_date=date(fiscal_year, 9, 30),
        is_open=True, is_closed=False,
    )
    db.add(period)
    db.flush()
    return period


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
    open_year(db)
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


def test_opening_revision_replaces_values_in_original_column_without_journal(db, monkeypatch):
    asset = account(db, "100-TEST", "ASSET", "DEBIT")
    liability = account(db, "200-TEST", "LIABILITY", "CREDIT")
    period = open_year(db)
    monkeypatch.setattr(module, "resolve_location_id", lambda *_args: 1)
    audits = []
    monkeypatch.setattr(module, "record_audit", lambda *_args, **kwargs: audits.append(kwargs))
    service = OpeningBalanceService(db)
    user = SimpleNamespace(id=1)
    service.post(
        user=user, fiscal_year=2026, location_id=1,
        lines=[{"account_id": asset.id, "amount": "125.00", "balance_type": "DEBIT"}],
        description=None,
    )
    original = service.list_entries(fiscal_year=2026, location_id=None)
    assert original["can_edit"] is True
    version = original["snapshot_version"]

    service.revise(
        user=user, fiscal_year=2026, location_id=1,
        expected_version=version,
        lines=[
            {"account_id": asset.id, "amount": "150.00", "balance_type": "DEBIT"},
            {"account_id": liability.id, "amount": "50.00", "balance_type": "CREDIT"},
        ],
        description="Adjusted from opening form",
    )
    saved = service.list_entries(fiscal_year=2026, location_id=None)
    assert saved["snapshot_version"] != version
    assert saved["total_debit"] == Decimal("150.00")
    assert saved["total_credit"] == Decimal("50.00")
    assert {(row["account_id"], row["balance_type"], row["amount"]) for row in saved["items"]} == {
        (asset.id, "DEBIT", Decimal("150.00")),
        (liability.id, "CREDIT", Decimal("50.00")),
    }
    assert db.query(JournalEntry).count() == 0
    assert all(row.journal_entry_id is None for row in db.query(OpeningBalance))
    assert audits[-1]["before_data"]["lines"][0]["amount"] == "125.00"
    assert audits[-1]["after_data"]["total_credit"] == "50.00"

    with pytest.raises(HTTPException) as stale:
        service.revise(
            user=user, fiscal_year=2026, location_id=1,
            expected_version=version, lines=[], description=None,
        )
    assert stale.value.status_code == 409

    service.revise(
        user=user, fiscal_year=2026, location_id=1,
        expected_version=saved["snapshot_version"],
        lines=[{"account_id": liability.id, "amount": "80.00", "balance_type": "DEBIT"}],
        description=None,
    )
    assert [(row.account_id, row.balance_type, row.amount) for row in db.query(OpeningBalance)] == [
        (liability.id, "DEBIT", Decimal("80.00"))
    ]

    period.is_open = False
    period.is_closed = True
    db.commit()
    assert service.list_entries(fiscal_year=2026, location_id=None)["can_edit"] is False
    with pytest.raises(HTTPException) as closed:
        service.revise(
            user=user, fiscal_year=2026, location_id=1,
            expected_version=service.list_entries(fiscal_year=2026, location_id=None)["snapshot_version"],
            lines=[], description=None,
        )
    assert closed.value.status_code == 400
    assert db.query(OpeningBalance).one().amount == Decimal("80.00")


def test_opening_initial_save_requires_open_year(db, monkeypatch):
    asset = account(db, "100-TEST", "ASSET", "DEBIT")
    monkeypatch.setattr(module, "resolve_location_id", lambda *_args: 1)
    monkeypatch.setattr(module, "record_audit", lambda *_args, **_kwargs: None)
    with pytest.raises(HTTPException) as closed:
        OpeningBalanceService(db).post(
            user=SimpleNamespace(id=1), fiscal_year=2026, location_id=1,
            lines=[{"account_id": asset.id, "amount": "12.00", "balance_type": "DEBIT"}],
            description=None,
        )
    assert closed.value.status_code == 400
    assert db.query(OpeningBalance).count() == 0
