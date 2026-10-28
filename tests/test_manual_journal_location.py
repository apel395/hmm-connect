from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1 import journals as journal_api
from app.models import Base
from app.models.business_unit import BusinessUnit
from app.models.chart_of_account import ChartOfAccount
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.location import Location
from app.schemas.journal import JournalCreate, JournalUpdate


ADMIN = SimpleNamespace(
    id=1, roles=[SimpleNamespace(name="SYSTEM_ADMINISTRATOR")],
    default_location_id=None, location_id=None,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    from app.models.fiscal_period import FiscalPeriod
    from calendar import monthrange
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    session.add(FiscalPeriod(fiscal_year=2026,fiscal_month=9,period_name='September 2026',start_date=date(2026,9,1),end_date=date(2026,9,30),is_open=True,is_closed=False,allow_backdated_entries=True))
    session.commit()
    yield session
    session.close()
    engine.dispose()


def test_manual_journal_requires_location_on_create(db):
    account = ChartOfAccount(
        account_number="JLOC-100", account_name="Test Account",
        account_type="ASSET", normal_balance="DEBIT",
        is_active=True, is_posting=True,
    )
    db.add(account)
    db.commit()
    data = JournalCreate(
        posting_date=date(2026, 9, 29),
        document_type="MANUAL_JOURNAL", document_number="JLOC-1",
        reference_type="MANUAL", reference_id=0,
        lines=[
            {"account_id": account.id, "debit": "100", "credit": "0"},
            {"account_id": account.id, "debit": "0", "credit": "100"},
        ],
    )
    with pytest.raises(HTTPException) as error:
        journal_api.create(data=data, db=db, user=ADMIN)
    assert error.value.status_code == 422
    assert "work location" in error.value.detail.lower()


def test_draft_manual_journal_location_repair_updates_header_and_lines(db, monkeypatch):
    monkeypatch.setattr(journal_api, "record_audit", lambda *_args, **_kwargs: None)
    unit = BusinessUnit(code="JLOC", name="Journal Location Test")
    db.add(unit)
    db.flush()
    location = Location(code="JLOC-OFFICE", name="Journal Office", business_unit_id=unit.id)
    account = ChartOfAccount(
        account_number="JLOC-200", account_name="Test Payable",
        account_type="LIABILITY", normal_balance="CREDIT",
        is_active=True, is_posting=True,
    )
    db.add_all([location, account])
    db.flush()
    journal = JournalEntry(
        journal_number="MAN-JLOC-1", posting_date=date(2026, 9, 29),
        status="DRAFT", reference_type="MANUAL", reference_id=0,
        business_unit_id=unit.id, location_id=None,
    )
    journal.lines = [
        JournalLine(account_id=account.id, debit=Decimal("100"), credit=Decimal("0"), business_unit_id=unit.id),
        JournalLine(account_id=account.id, debit=Decimal("0"), credit=Decimal("100"), business_unit_id=unit.id),
    ]
    db.add(journal)
    db.commit()

    result = journal_api.update(
        journal_id=journal.id, data=JournalUpdate(location_id=location.id),
        db=db, user=ADMIN,
    )
    db.refresh(journal)
    assert result["location_id"] == location.id
    assert result["location_name"] == "Journal Office"
    assert {line.location_id for line in journal.lines} == {location.id}
