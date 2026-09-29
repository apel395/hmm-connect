from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.payments import create, eligible, listing, result, invoice_balance, reserved_amount
from app.models import Base
from app.models.bank_account import BankAccount
from app.models.chart_of_account import ChartOfAccount
from app.models.purchase_order import PurchaseOrder
from app.models.payment import Payment
from app.models.supplier import Supplier
from app.models.supplier_invoice import SupplierInvoice, SupplierInvoiceLine
from app.schemas.payment import PaymentCreate
from app.schemas.supplier_invoice import SupplierInvoiceInput


ADMIN = SimpleNamespace(
    id=1, roles=[SimpleNamespace(name="SYSTEM_ADMINISTRATOR")],
    default_location_id=None, location_id=None,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()
    engine.dispose()


def test_tax_inclusive_invoice_remains_unchanged_when_payment_draft_is_created(db):
    supplier = Supplier(code="PAY-TAX", name="Payment Tax Supplier", is_active=True)
    account = ChartOfAccount(
        account_number="PAY-TAX-BANK", account_name="Payment Bank",
        account_type="ASSET", account_subtype="BANK", normal_balance="DEBIT",
        is_active=True, is_posting=True,
    )
    db.add_all([supplier, account])
    db.flush()
    order = PurchaseOrder(po_number="PAY-TAX-PO", supplier_id=supplier.id, location_id=1)
    bank = BankAccount(
        bank_name="Test Bank", account_name="Operating", account_number="PAY-TAX-ACCOUNT",
        coa_account_id=account.id, business_unit_id=1, currency="IDR",
        is_active=True, is_payment_account=True,
    )
    db.add_all([order, bank])
    db.flush()
    invoice_input = SupplierInvoiceInput(
        supplier_id=supplier.id, supplier_invoice_number="PAY-TAX-INV",
        invoice_date=date(2026, 9, 29), business_unit_id=1, location_id=1,
        lines=[{
            "description": "Taxable supply", "quantity": 1, "unit_price": 100,
            "is_taxable": True, "tax_rate": 11,
        }],
    )
    assert invoice_input.tax_amount == Decimal("11")
    assert invoice_input.total_amount == Decimal("111")
    invoice = SupplierInvoice(
        internal_invoice_number="PAY-TAX-INTERNAL", supplier_invoice_number="PAY-TAX-INV",
        supplier_id=supplier.id, purchase_order_id=order.id,
        invoice_date=date(2026, 9, 29), business_unit_id=1, location_id=1,
        currency="IDR", subtotal=Decimal("100"), tax_amount=Decimal("11"),
        total_amount=Decimal("111"), paid_amount=Decimal("0"),
        balance_amount=Decimal("111"), status="POSTED",
    )
    invoice.lines.append(SupplierInvoiceLine(
        description="Taxable supply", quantity=Decimal("1"), unit_price=Decimal("100"),
        line_amount=Decimal("100"), is_taxable=True, tax_rate=Decimal("11"),
        tax_amount=Decimal("11"),
    ))
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    assert invoice.total_amount == Decimal("111")
    assert invoice.paid_amount == Decimal("0")
    assert invoice.adjustment_amount == Decimal("0")
    assert invoice_balance(invoice) == Decimal("111")
    assert reserved_amount(db, invoice.id) == Decimal("0")

    payment = create(
        data=PaymentCreate(
            supplier_id=supplier.id, payment_date=date(2026, 9, 29),
            total_amount=Decimal("111"),
            allocations=[{"supplier_invoice_id": invoice.id, "allocated_amount": "111"}],
            funding_lines=[{"bank_account_id": bank.id, "amount": "111"}],
        ),
        db=db, user=ADMIN,
    )
    db.refresh(invoice)
    assert payment["status"] == "DRAFT"
    assert payment["total_amount"] == Decimal("111")
    assert payment["allocations"][0]["invoice_tax_amount"] == Decimal("11")
    assert payment["allocations"][0]["current_invoice_total"] == Decimal("111")
    assert invoice.total_amount == Decimal("111")
    assert invoice.tax_amount == Decimal("11")
    assert invoice.paid_amount == Decimal("0")

    with pytest.raises(HTTPException) as conflict:
        create(
            data=PaymentCreate(
                supplier_id=supplier.id, payment_date=date(2026, 9, 29),
                total_amount=Decimal("111"),
                allocations=[{"supplier_invoice_id": invoice.id, "allocated_amount": "111"}],
                funding_lines=[{"bank_account_id": bank.id, "amount": "111"}],
            ),
            db=db, user=ADMIN,
        )
    assert conflict.value.status_code == 409
    assert payment["payment_number"] in conflict.value.detail

    choices = eligible(supplier_id=supplier.id, currency="IDR", db=db, user=ADMIN)
    assert choices[0]["available_balance"] == Decimal("111")
    assert choices[0]["tax_amount"] == Decimal("11")
    payments = listing(
        page=1, page_size=20, search=None, supplier_id=None, status=None,
        payment_method=None, payment_date_from=None, payment_date_to=None,
        location_id=None, db=db, user=ADMIN,
    )
    assert payments["summary"]["total_amount"] == Decimal("111")

    # Posted payments have already reduced the invoice's outstanding balance.
    # Their own allocation must not show as a new availability exception.
    posted = db.get(Payment, payment["id"])
    posted.status = "POSTED"
    invoice.paid_amount = Decimal("111")
    db.commit()
    posted_view = result(db, posted, ADMIN)
    assert posted_view["allocation_exception"] is False
    assert posted_view["allocations"][0]["current_available_balance"] == Decimal("111")

    # A reopened draft must reflect a different approved payment's reservation.
    posted.status = "VOID"
    invoice.paid_amount = Decimal("0")
    db.commit()
    other = create(
        data=PaymentCreate(
            supplier_id=supplier.id, payment_date=date(2026, 9, 29),
            total_amount=Decimal("111"),
            allocations=[{"supplier_invoice_id": invoice.id, "allocated_amount": "111"}],
            funding_lines=[{"bank_account_id": bank.id, "amount": "111"}],
        ),
        db=db, user=ADMIN,
    )
    db.get(Payment, other["id"]).status = "APPROVED"
    posted.status = "DRAFT"  # Simulate an older overlapping draft after the new guard.
    db.commit()
    reopened_view = result(db, posted, ADMIN)
    assert reopened_view["allocation_exception"] is True
    assert reopened_view["allocations"][0]["current_reserved_amount"] == Decimal("111")
    assert reopened_view["allocations"][0]["current_available_balance"] == Decimal("0")
    assert reopened_view["allocations"][0]["reserved_by_payments"][0]["id"] == other["id"]
