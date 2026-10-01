from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.ap_movement import listing
from app.models import Base
from app.models.accounting_posting_rule import AccountingPostingRule
from app.models.chart_of_account import ChartOfAccount
from app.models.opening_balance import OpeningBalance
from app.models.payment import Payment, PaymentAllocation
from app.models.supplier import Supplier
from app.models.supplier_invoice import SupplierInvoice


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()
    engine.dispose()


def report(db, user, **kwargs):
    return listing(
        db=db, user=user, page=kwargs.pop("page", 1),
        page_size=kwargs.pop("page_size", 50),
        date_from=kwargs.pop("date_from", date(2026, 1, 1)),
        date_to=kwargs.pop("date_to", date(2026, 12, 31)),
        **kwargs,
    )


def setup(db):
    inventory = ChartOfAccount(
        account_number="1100", account_name="Inventory", account_type="ASSET",
        normal_balance="DEBIT", is_posting=True, is_active=True,
    )
    payable = ChartOfAccount(
        account_number="2100", account_name="AP", account_type="LIABILITY",
        normal_balance="CREDIT", is_posting=True, is_active=True,
    )
    supplier = Supplier(code="SUP-1", name="Supplier", is_active=True)
    other = Supplier(code="SUP-2", name="Other", is_active=True)
    db.add_all([inventory, payable, supplier, other])
    db.flush()
    db.add(AccountingPostingRule(
        event_type="SUPPLIER_INVOICE_INVENTORY",
        debit_account_id=inventory.id, credit_account_id=payable.id, is_active=True,
    ))
    db.add(OpeningBalance(
        fiscal_year=2026, account_id=payable.id, amount=Decimal("200"),
        balance_type="CREDIT",
    ))
    invoice = SupplierInvoice(
        internal_invoice_number="INV-1", supplier_invoice_number="EXT-1",
        supplier_id=supplier.id, invoice_date=date(2026, 1, 5),
        subtotal=Decimal("100"), total_amount=Decimal("100"), status="POSTED",
    )
    other_invoice = SupplierInvoice(
        internal_invoice_number="INV-2", supplier_invoice_number="EXT-2",
        supplier_id=other.id, invoice_date=date(2026, 1, 5),
        subtotal=Decimal("50"), total_amount=Decimal("50"), status="POSTED",
    )
    db.add_all([invoice, other_invoice])
    db.flush()
    payment = Payment(
        payment_number="PAY-1", payment_date=date(2026, 1, 7),
        amount=Decimal("40"), payment_method="TRANSFER", status="POSTED",
        supplier_id=supplier.id, created_by_id=1,
    )
    payment.allocations.append(PaymentAllocation(
        supplier_invoice_id=invoice.id, allocated_amount=Decimal("30"),
    ))
    db.add(payment)
    db.commit()
    admin = SimpleNamespace(id=99, roles=[SimpleNamespace(name="SYSTEM_ADMINISTRATOR")])
    return admin, supplier, invoice


def test_opening_invoice_payment_and_unallocated_amount(db):
    admin, supplier, invoice = setup(db)
    assert [(row.id, row.status, row.invoice_date) for row in db.query(SupplierInvoice).all()] == [
        (invoice.id, "POSTED", date(2026, 1, 5)),
        (invoice.id + 1, "POSTED", date(2026, 1, 5)),
    ]
    result = report(db, admin)
    assert [row["document_number"] for row in result["items"]] == [
        "Opening AP", "INV-1", "INV-2", "PAY-1",
    ]
    summary = result["summary"]
    assert summary["opening_balance"] == Decimal("200")
    assert summary["invoice_total"] == Decimal("150")
    assert summary["payment_total"] == Decimal("40")
    assert summary["closing_balance"] == Decimal("310")
    assert result["items"][0]["movement_type"] == "OPENING"
    payment = next(row for row in result["items"] if row["movement_type"] == "PAYMENT")
    assert payment["unallocated_amount"] == Decimal("10")
    assert payment["running_balance"] == Decimal("310")
    assert report(db, admin, movement_type="OPENING")["total_items"] == 1


def test_supplier_scope_does_not_attribute_account_opening(db):
    admin, supplier, invoice = setup(db)
    result = report(db, admin, supplier_id=supplier.id)
    assert result["summary"]["opening_balance"] == Decimal("0")
    assert result["summary"]["opening_unassigned"] is True
    assert result["summary"]["closing_balance"] == Decimal("60")
    assert result["summary"]["invoice_total"] == Decimal("100")


def test_period_start_and_pagination_keep_full_running_balance(db):
    admin, supplier, invoice = setup(db)
    result = report(db, admin, date_from=date(2026, 1, 6), page=2, page_size=1)
    assert result["summary"]["opening_balance"] == Decimal("350")
    assert result["summary"]["closing_balance"] == Decimal("310")
    assert result["items"][0]["movement_type"] == "PAYMENT"
    assert result["items"][0]["running_balance"] == Decimal("310")


def test_ap_user_sees_only_own_paid_documents_and_no_account_opening(db):
    admin, supplier, invoice = setup(db)
    ap_user = SimpleNamespace(
        id=1, default_location_id=None, location_id=None,
        roles=[SimpleNamespace(
            name="AP", permissions=[SimpleNamespace(code="ap.view")],
        )],
    )
    result = report(db, ap_user)
    assert result["summary"]["opening_unassigned"] is True
    assert result["summary"]["invoice_total"] == Decimal("100")
    assert result["summary"]["closing_balance"] == Decimal("60")
    assert {row["document_number"] for row in result["items"]} == {
        "Brought forward", "INV-1", "PAY-1",
    }
