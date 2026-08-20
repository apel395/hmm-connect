from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.payment import Payment, PaymentAllocation
from app.models.supplier import Supplier
from app.models.supplier_invoice import SupplierInvoice
from app.models.user import User
from app.services.ap_reporting_service import APReportingService


def make_db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def seed_invoice(db, *, status="POSTED", total="100000", supplier_code="SUP-1"):
    supplier = db.query(Supplier).filter(Supplier.code == supplier_code).first()
    if not supplier:
        supplier = Supplier(code=supplier_code, name=f"Supplier {supplier_code}", is_active=True)
        db.add(supplier)
        db.flush()
    invoice = SupplierInvoice(
        internal_invoice_number=f"INV-{status}-{supplier_code}",
        supplier_invoice_number=f"EXT-{status}-{supplier_code}",
        supplier_id=supplier.id,
        invoice_date=date(2026, 8, 20),
        due_date=date(2026, 8, 25),
        subtotal=Decimal(total),
        total_amount=Decimal(total),
        paid_amount=Decimal("0"),
        adjustment_amount=Decimal("0"),
        balance_amount=Decimal(total),
        status=status,
    )
    db.add(invoice)
    db.flush()
    return supplier, invoice


def test_summary_uses_only_posted_invoices_and_posted_payments():
    db = make_db()
    user = User(username="finance", email="finance@example.test", full_name="Finance", password_hash="x", is_active=True)
    db.add(user)
    db.flush()
    supplier, invoice = seed_invoice(db, status="POSTED", total="100000")
    seed_invoice(db, status="DRAFT", total="50000", supplier_code="SUP-2")

    payment = Payment(
        payment_number="PAY-1",
        payment_date=date(2026, 8, 20),
        amount=Decimal("40000"),
        payment_method="BANK_TRANSFER",
        status="POSTED",
        created_by_id=user.id,
        supplier_id=supplier.id,
    )
    db.add(payment)
    db.flush()
    db.add(PaymentAllocation(payment_id=payment.id, supplier_invoice_id=invoice.id, allocated_amount=Decimal("40000")))
    db.commit()

    report = APReportingService(db).summary()
    assert report["metrics"]["gross_payables"] == Decimal("100000")
    assert report["metrics"]["total_payments"] == Decimal("40000")
    assert report["metrics"]["outstanding_payables"] == Decimal("60000")
    assert report["metrics"]["supplier_count"] == 1
    assert report["items"][0]["status"] == "PARTIALLY_PAID"
    db.close()


def test_detail_statuses_follow_posted_payment_allocations():
    db = make_db()
    user = User(username="finance2", email="finance2@example.test", full_name="Finance 2", password_hash="x", is_active=True)
    db.add(user)
    db.flush()
    supplier, invoice = seed_invoice(db, status="POSTED", total="55500", supplier_code="SUP-X")
    payment = Payment(
        payment_number="PAY-X",
        payment_date=date(2026, 8, 20),
        amount=Decimal("55500"),
        payment_method="BANK_TRANSFER",
        status="POSTED",
        created_by_id=user.id,
        supplier_id=supplier.id,
    )
    db.add(payment)
    db.flush()
    db.add(PaymentAllocation(payment_id=payment.id, supplier_invoice_id=invoice.id, allocated_amount=Decimal("55500")))
    db.commit()

    report = APReportingService(db).detail()
    row = report["items"][0]
    assert row["gross_amount"] == Decimal("55500")
    assert row["paid_amount"] == Decimal("55500")
    assert row["outstanding_amount"] == Decimal("0.00")
    assert row["status"] == "PAID"
    db.close()
