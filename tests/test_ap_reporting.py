from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.services.ap_reporting_service as reporting_module
from app.api.v1.ap_reporting import _require_access, router
from app.api.v1.ap_aging import _aging_data
from app.models import Base
from app.models.account_payable import AccountPayable
from app.models.business_unit import BusinessUnit
from app.models.chart_of_account import ChartOfAccount
from app.models.department import Department
from app.models.inventory import Inventory
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.location import Location
from app.models.payment import Payment, PaymentAllocation
from app.models.supplier import Supplier
from app.models.supplier_adjustment import SupplierAdjustment
from app.models.supplier_invoice import SupplierInvoice, SupplierInvoiceLine
from app.models.user import User
from app.services.ap_reporting_service import APReportingService, _bucket

TODAY = date(2026, 8, 20)


@pytest.fixture
def ap_db(monkeypatch):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return TODAY

    monkeypatch.setattr(reporting_module, "date", FixedDate)
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    user = User(username="finance", email="finance@example.test", full_name="Finance", password_hash="x", is_active=True)
    account = ChartOfAccount(account_number="5100", account_name="Adjustment", account_type="EXPENSE", normal_balance="DEBIT", is_posting=True, is_active=True)
    db.add_all([user, account]); db.flush()
    yield db, user, account
    db.close()


def supplier(db, code="SUP-1", name=None):
    row = db.query(Supplier).filter(Supplier.code == code).first()
    if not row:
        row = Supplier(code=code, name=name or f"Supplier {code}", is_active=True)
        db.add(row); db.flush()
    return row


def invoice(db, *, number, supplier_row=None, status="POSTED", total="10000000", due_date=TODAY, business_unit_id=None, location_id=None, department_id=None):
    supplier_row = supplier_row or supplier(db)
    amount = Decimal(total)
    row = SupplierInvoice(
        internal_invoice_number=number, supplier_invoice_number=f"EXT-{number}",
        supplier_id=supplier_row.id, invoice_date=TODAY, due_date=due_date,
        subtotal=amount, total_amount=amount, paid_amount=Decimal("0"),
        adjustment_amount=Decimal("0"), balance_amount=amount, status=status,
        business_unit_id=business_unit_id, location_id=location_id, department_id=department_id,
    )
    row.lines.append(SupplierInvoiceLine(description="AP fixture", quantity=Decimal("1"), unit_price=amount, line_amount=amount))
    db.add(row); db.flush()
    return row


def payment(db, user, *, number, supplier_row, status, allocations):
    total = sum((Decimal(amount) for _, amount in allocations), Decimal("0"))
    row = Payment(payment_number=number, payment_date=TODAY, amount=total, payment_method="BANK_TRANSFER", status=status, created_by_id=user.id, supplier_id=supplier_row.id)
    db.add(row); db.flush()
    for invoice_row, amount in allocations:
        db.add(PaymentAllocation(payment_id=row.id, supplier_invoice_id=invoice_row.id, allocated_amount=Decimal(amount)))
    return row


def adjustment(db, user, account, *, number, invoice_row, status, amount="1000000", kind="CREDIT_NOTE"):
    row = SupplierAdjustment(
        adjustment_number=number, adjustment_type=kind, supplier_invoice_id=invoice_row.id,
        supplier_id=invoice_row.supplier_id, adjustment_date=TODAY, amount=Decimal(amount),
        adjustment_account_id=account.id, reason="Fixture", status=status, created_by_id=user.id,
    )
    db.add(row)
    return row


def test_recognition_and_payment_states(ap_db):
    db, user, _ = ap_db
    vendor = supplier(db)
    posted = invoice(db, number="POSTED", supplier_row=vendor)
    for state in ("VERIFIED", "DRAFT", "VOID"):
        invoice(db, number=state, supplier_row=vendor, status=state)
    payment(db, user, number="PAY-POSTED", supplier_row=vendor, status="POSTED", allocations=[(posted, "4000000")])
    for state in ("DRAFT", "APPROVED", "VOID"):
        payment(db, user, number=f"PAY-{state}", supplier_row=vendor, status=state, allocations=[(posted, "500000")])
    db.commit()
    metrics = APReportingService(db).summary()["metrics"]
    assert metrics["gross_payables"] == Decimal("10000000")
    assert metrics["total_payments"] == Decimal("4000000")
    assert metrics["outstanding_payables"] == Decimal("6000000")


@pytest.mark.parametrize(("paid", "outstanding", "status"), [
    ("0", "10000000", "UNPAID"), ("4000000", "6000000", "PARTIALLY_PAID"), ("10000000", "0", "PAID"),
])
def test_unpaid_partial_and_fully_paid_history(ap_db, paid, outstanding, status):
    db, user, _ = ap_db
    vendor = supplier(db); row = invoice(db, number=f"INV-{paid}", supplier_row=vendor)
    if Decimal(paid):
        payment(db, user, number=f"PAY-{paid}", supplier_row=vendor, status="POSTED", allocations=[(row, paid)])
    db.commit()
    detail = APReportingService(db).detail()["items"][0]
    aging = APReportingService(db).aging()
    assert (detail["paid_amount"], detail["outstanding_amount"], detail["status"]) == (Decimal(paid), Decimal(outstanding), status)
    assert aging["total_outstanding"] == Decimal(outstanding)
    assert aging["total_items"] == (1 if Decimal(outstanding) else 0)


def test_multiple_payments_and_multiple_allocations_are_not_duplicated(ap_db):
    db, user, _ = ap_db
    vendor = supplier(db); first = invoice(db, number="INV-1", supplier_row=vendor); second = invoice(db, number="INV-2", supplier_row=vendor, total="2000000")
    payment(db, user, number="PAY-1", supplier_row=vendor, status="POSTED", allocations=[(first, "3000000"), (second, "1000000")])
    payment(db, user, number="PAY-2", supplier_row=vendor, status="POSTED", allocations=[(first, "2000000")]); db.commit()
    rows = {row["invoice_number"]: row for row in APReportingService(db).detail()["items"]}
    assert rows["INV-1"]["paid_amount"] == Decimal("5000000")
    assert rows["INV-1"]["outstanding_amount"] == Decimal("5000000")
    assert rows["INV-2"]["paid_amount"] == Decimal("1000000")


@pytest.mark.parametrize("kind", ["CREDIT_NOTE", "DEBIT_NOTE"])
def test_only_posted_adjustments_reduce_outstanding(ap_db, kind):
    db, user, account = ap_db
    vendor = supplier(db); row = invoice(db, number="INV-ADJ", supplier_row=vendor)
    payment(db, user, number="PAY-ADJ", supplier_row=vendor, status="POSTED", allocations=[(row, "4000000")])
    adjustment(db, user, account, number="ADJ-POSTED", invoice_row=row, status="POSTED", kind=kind)
    adjustment(db, user, account, number="ADJ-DRAFT", invoice_row=row, status="DRAFT", amount="500000")
    adjustment(db, user, account, number="ADJ-VOID", invoice_row=row, status="VOID", amount="500000"); db.commit()
    detail = APReportingService(db).detail()["items"][0]
    assert detail["adjustment_amount"] == Decimal("1000000")
    assert detail["outstanding_amount"] == Decimal("5000000")


@pytest.mark.parametrize(("days", "expected"), [
    (0, "current"), (1, "1_30"), (30, "1_30"), (31, "31_60"), (60, "31_60"), (61, "61_90"), (90, "61_90"), (91, "over_90"),
])
def test_aging_boundaries(days, expected):
    assert _bucket(days) == expected


def test_aging_uses_outstanding_and_due_today_is_current(ap_db):
    db, user, _ = ap_db
    vendor = supplier(db); current = invoice(db, number="DUE-TODAY", supplier_row=vendor); paid = invoice(db, number="OLD", supplier_row=vendor, total="2000000", due_date=TODAY - timedelta(days=91))
    payment(db, user, number="PAY-CURRENT", supplier_row=vendor, status="POSTED", allocations=[(current, "4000000")])
    payment(db, user, number="PAY-OLD", supplier_row=vendor, status="POSTED", allocations=[(paid, "2000000")]); db.commit()
    aging = APReportingService(db).aging()
    assert aging["buckets"]["current"]["amount"] == Decimal("6000000")
    assert aging["buckets"]["over_90"]["amount"] == Decimal("0")


def test_summary_detail_supplier_and_aging_invariants(ap_db):
    db, user, _ = ap_db
    first_vendor = supplier(db, "SUP-A"); second_vendor = supplier(db, "SUP-B")
    first = invoice(db, number="INV-A", supplier_row=first_vendor); invoice(db, number="INV-B", supplier_row=second_vendor, total="3000000", due_date=TODAY - timedelta(days=31))
    payment(db, user, number="PAY-A", supplier_row=first_vendor, status="POSTED", allocations=[(first, "2500000")]); db.commit()
    service = APReportingService(db); summary = service.summary(page_size=1); detail = service.detail(page_size=100); aging = service.aging(page_size=100); metrics = summary["metrics"]
    assert sum((row["gross_amount"] for row in detail["items"]), Decimal("0")) == metrics["gross_payables"]
    assert sum((row["paid_amount"] for row in detail["items"]), Decimal("0")) == metrics["total_payments"]
    assert sum((row["outstanding_amount"] for row in detail["items"]), Decimal("0")) == metrics["outstanding_payables"]
    assert sum((row["outstanding_amount"] for row in service.summary(page_size=100)["items"]), Decimal("0")) == metrics["outstanding_payables"]
    assert sum((bucket["amount"] for bucket in aging["buckets"].values()), Decimal("0")) == metrics["outstanding_payables"]


def test_new_aging_agrees_with_existing_aging_for_equivalent_lifecycle_state(ap_db):
    db, user, account = ap_db
    vendor = supplier(db); row = invoice(db, number="AGING-COMPARE", supplier_row=vendor)
    payment(db, user, number="PAY-COMPARE", supplier_row=vendor, status="POSTED", allocations=[(row, "4000000")])
    adjustment(db, user, account, number="ADJ-COMPARE", invoice_row=row, status="POSTED")
    row.paid_amount = Decimal("4000000"); row.adjustment_amount = Decimal("1000000")
    entry = JournalEntry(journal_number="JE-COMPARE", posting_date=TODAY, status="POSTED", reference_type="SUPPLIER_INVOICE", reference_id=row.id)
    entry.lines.append(JournalLine(account_id=account.id, debit=Decimal("10000000"), credit=Decimal("0")))
    db.add(entry); db.commit()
    new_aging = APReportingService(db).aging()
    existing_aging, _ = _aging_data(db)
    assert new_aging["total_outstanding"] == Decimal("5000000")
    assert existing_aging["metrics"]["total_outstanding"] == new_aging["total_outstanding"]


def test_filters_are_consistent_and_searches_supplier(ap_db):
    db, _, _ = ap_db
    bu1 = BusinessUnit(code="BU-1", name="Business Unit 1", is_active=True); bu2 = BusinessUnit(code="BU-2", name="Business Unit 2", is_active=True)
    db.add_all([bu1, bu2]); db.flush()
    loc1 = Location(code="LOC-1", name="Location 1", business_unit_id=bu1.id, is_active=True); loc2 = Location(code="LOC-2", name="Location 2", business_unit_id=bu2.id, is_active=True)
    dep1 = Department(code="DEP-1", name="Department 1", business_unit_id=bu1.id, is_active=True); dep2 = Department(code="DEP-2", name="Department 2", business_unit_id=bu2.id, is_active=True)
    db.add_all([loc1, loc2, dep1, dep2]); db.flush()
    target = supplier(db, "TARGET", "Long Target Supplier Name"); other = supplier(db, "OTHER")
    invoice(db, number="TARGET-INVOICE", supplier_row=target, business_unit_id=bu1.id, location_id=loc1.id, department_id=dep1.id)
    invoice(db, number="OTHER-INVOICE", supplier_row=other, business_unit_id=bu2.id, location_id=loc2.id, department_id=dep2.id); db.commit()
    filters = {"business_unit_id": bu1.id, "location_id": loc1.id, "department_id": dep1.id, "search": "Target Supplier"}; service = APReportingService(db)
    assert service.summary(**filters)["metrics"]["invoice_count"] == 1
    assert service.detail(**filters)["total_items"] == 1
    assert service.aging(**filters)["total_items"] == 1
    assert service.summary(supplier_id=other.id)["items"][0]["supplier_id"] == other.id


@pytest.mark.parametrize("role", ["SYSTEM_ADMINISTRATOR", "FINANCE", "GENERAL_MANAGER", "AUDITOR"])
def test_authorized_reporting_roles(role):
    permissions = [] if role == "SYSTEM_ADMINISTRATOR" else [SimpleNamespace(code="finance.view")]
    _require_access(SimpleNamespace(roles=[SimpleNamespace(name=role, permissions=permissions)]))


def test_unauthorized_role_and_get_only_routes():
    with pytest.raises(HTTPException) as denied:
        _require_access(SimpleNamespace(roles=[SimpleNamespace(name="WAREHOUSE", permissions=[])]))
    assert denied.value.status_code == 403
    assert all(route.methods == {"GET"} for route in router.routes)


def test_reporting_performs_zero_accounting_mutations(ap_db):
    db, user, account = ap_db
    vendor = supplier(db); row = invoice(db, number="READ-ONLY", supplier_row=vendor)
    payment(db, user, number="PAY-READ-ONLY", supplier_row=vendor, status="POSTED", allocations=[(row, "1000000")])
    adjustment(db, user, account, number="ADJ-READ-ONLY", invoice_row=row, status="POSTED"); db.commit()
    models = (SupplierInvoice, Payment, PaymentAllocation, AccountPayable, JournalEntry, JournalLine, Inventory, SupplierAdjustment)
    before = {model: db.query(model).count() for model in models}
    service = APReportingService(db); service.summary(); service.detail(); service.aging()
    assert {model: db.query(model).count() for model in models} == before
    assert not db.new and not db.dirty and not db.deleted
