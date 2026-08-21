from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.services.ar_reporting_service as reporting_module
from app.api.v1.ar_reporting import _require_access, router
from app.models import Base
from app.models.account_receivable import AccountReceivable
from app.models.customer import Customer
from app.models.customer_payment import CustomerPayment
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.services.ar_reporting_service import ARReportingService, _bucket

TODAY = date(2026, 8, 21)


@pytest.fixture
def ar_db(monkeypatch):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return TODAY

    monkeypatch.setattr(reporting_module, "date", FixedDate)
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    yield db
    db.close()


def customer(db, code="CUS-1", name="Customer"):
    row = Customer(customer_code=code, customer_name=name, is_active=True)
    db.add(row)
    db.flush()
    return row


def invoice(
    db,
    customer_row,
    number,
    *,
    total="10000000",
    received="0",
    outstanding=None,
    due_date=TODAY,
):
    total_value = Decimal(total)
    received_value = Decimal(received)
    row = AccountReceivable(
        invoice_number=number,
        customer_id=customer_row.id,
        invoice_date=TODAY,
        due_date=due_date,
        amount=total_value,
        received_amount=received_value,
        outstanding_amount=(
            Decimal(outstanding)
            if outstanding is not None
            else total_value - received_value
        ),
        status="PAID" if received_value == total_value else "PARTIAL" if received_value else "UNPAID",
    )
    db.add(row)
    db.flush()
    return row


@pytest.mark.parametrize(("received", "expected_outstanding", "status"), [
    ("0", "10000000", "UNPAID"),
    ("4000000", "6000000", "PARTIALLY_PAID"),
    ("10000000", "0", "PAID"),
])
def test_receivable_states(ar_db, received, expected_outstanding, status):
    client = customer(ar_db)
    invoice(ar_db, client, f"AR-{received}", received=received)
    ar_db.commit()

    detail = ARReportingService(ar_db).detail()["items"][0]
    aging = ARReportingService(ar_db).aging()

    assert detail["received_amount"] == Decimal(received)
    assert detail["outstanding_amount"] == Decimal(expected_outstanding)
    assert detail["status"] == status
    assert aging["total_outstanding"] == Decimal(expected_outstanding)


@pytest.mark.parametrize(("days", "expected"), [
    (0, "current"), (1, "1_30"), (30, "1_30"), (31, "31_60"),
    (60, "31_60"), (61, "61_90"), (90, "61_90"), (91, "over_90"),
])
def test_aging_boundaries(days, expected):
    assert _bucket(days) == expected


def test_summary_detail_and_aging_totals_are_consistent(ar_db):
    first = customer(ar_db, "CUS-A", "Alpha")
    second = customer(ar_db, "CUS-B", "Beta")
    invoice(ar_db, first, "AR-A", received="2500000")
    invoice(
        ar_db,
        second,
        "AR-B",
        total="3000000",
        due_date=TODAY - timedelta(days=31),
    )
    ar_db.commit()

    service = ARReportingService(ar_db)
    summary = service.summary(page_size=100)
    detail = service.detail(page_size=100)
    aging = service.aging(page_size=100)

    assert sum((row["gross_amount"] for row in detail["items"]), Decimal("0")) == summary["metrics"]["gross_receivables"]
    assert sum((row["received_amount"] for row in detail["items"]), Decimal("0")) == summary["metrics"]["total_receipts"]
    assert sum((row["outstanding_amount"] for row in detail["items"]), Decimal("0")) == summary["metrics"]["outstanding_receivables"]
    assert sum((row["outstanding_amount"] for row in summary["items"]), Decimal("0")) == summary["metrics"]["outstanding_receivables"]
    assert sum((row["amount"] for row in aging["buckets"].values()), Decimal("0")) == summary["metrics"]["outstanding_receivables"]


def test_filters_pagination_and_search(ar_db):
    alpha = customer(ar_db, "CUS-A", "Alpha Customer")
    beta = customer(ar_db, "CUS-B", "Beta Customer")
    invoice(ar_db, alpha, "AR-ALPHA")
    invoice(ar_db, beta, "AR-BETA")
    ar_db.commit()

    service = ARReportingService(ar_db)
    assert service.summary(customer_id=beta.id)["items"][0]["customer_id"] == beta.id
    assert service.detail(search="Alpha Customer")["items"][0]["invoice_number"] == "AR-ALPHA"
    assert service.detail(page_size=1)["total_pages"] == 2


@pytest.mark.parametrize("role", ["SYSTEM_ADMINISTRATOR", "FINANCE", "GENERAL_MANAGER", "AUDITOR"])
def test_authorized_roles(role):
    _require_access(SimpleNamespace(roles=[SimpleNamespace(name=role)]))


def test_unauthorized_and_get_only():
    with pytest.raises(HTTPException) as denied:
        _require_access(SimpleNamespace(roles=[SimpleNamespace(name="WAREHOUSE")]))
    assert denied.value.status_code == 403
    assert all(route.methods == {"GET"} for route in router.routes)


def test_reporting_is_read_only(ar_db):
    client = customer(ar_db)
    row = invoice(ar_db, client, "AR-READ-ONLY", received="1000000")
    ar_db.add(CustomerPayment(
        payment_number="CP-1",
        account_receivable_id=row.id,
        payment_date=TODAY,
        amount=Decimal("1000000"),
        payment_method="BANK_TRANSFER",
        status="POSTED",
    ))
    ar_db.commit()
    models = (AccountReceivable, CustomerPayment, JournalEntry, JournalLine)
    before = {model: ar_db.query(model).count() for model in models}

    service = ARReportingService(ar_db)
    service.summary()
    service.detail()
    service.aging()

    assert {model: ar_db.query(model).count() for model in models} == before
    assert not ar_db.new and not ar_db.dirty and not ar_db.deleted

