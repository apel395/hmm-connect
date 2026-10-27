from datetime import date
from decimal import Decimal

from app.api.v1.payments import invoice_balance, ready_to_pay
from app.models.payment import Payment, PaymentAllocation
from app.models.supplier import Supplier
from app.models.supplier_invoice import SupplierInvoice, SupplierInvoiceLine
from test_payment_tax_flow import ADMIN, db


def test_ready_to_pay_excludes_drafts_paid_invoices_and_reserved_balances(db):
    supplier = Supplier(code="QUEUE-SUPP", name="Supplier Ready to Pay", is_active=True)
    db.add(supplier)
    db.flush()

    def invoice(number, status, paid=0):
        row = SupplierInvoice(
            internal_invoice_number=number,
            supplier_invoice_number=f"V-{number}",
            supplier_id=supplier.id,
            invoice_date=date(2026, 10, 21),
            due_date=date(2026, 10, 28),
            currency="IDR",
            subtotal=Decimal("100"),
            total_amount=Decimal("100"),
            paid_amount=Decimal(str(paid)),
            status=status,
        )
        row.lines.append(SupplierInvoiceLine(
            description="Received stock", quantity=1,
            unit_price=Decimal("100"), line_amount=Decimal("100"),
        ))
        db.add(row)
        db.flush()
        return row

    eligible = invoice("INV-QUEUE-1", "POSTED")
    invoice("INV-QUEUE-DRAFT", "DRAFT")
    invoice("INV-QUEUE-PAID", "POSTED", 100)
    reserved = invoice("INV-QUEUE-RESERVED", "POSTED")
    payment = Payment(
        payment_number="PAY-QUEUE-1", supplier_id=supplier.id,
        payment_date=date(2026, 10, 22), amount=Decimal("85"),
        payment_method="BANK_TRANSFER", status="APPROVED", created_by_id=1,
    )
    payment.allocations.append(PaymentAllocation(
        supplier_invoice_id=reserved.id, allocated_amount=Decimal("85"),
    ))
    db.add(payment)
    db.commit()
    assert db.query(SupplierInvoice).count() == 4
    assert db.query(SupplierInvoice).filter(SupplierInvoice.status == "POSTED").count() == 3
    assert db.query(SupplierInvoice).filter(SupplierInvoice.status == "POSTED", SupplierInvoice.currency == "IDR").count() == 3
    assert invoice_balance(eligible) == Decimal("100"), (eligible.total_amount, eligible.paid_amount, eligible.adjustment_amount)

    page = ready_to_pay(page=1, page_size=50, search=None, currency="IDR", db=db, user=ADMIN)
    assert page["total_items"] == 2
    assert [item["id"] for item in page["items"]] == [eligible.id, reserved.id]
    assert [item["available_balance"] for item in page["items"]] == [Decimal("100"), Decimal("15")]
    assert page["totals_by_currency"] == {"IDR": Decimal("115")}

    filtered = ready_to_pay(page=1, page_size=50, search="RESERVED", currency="IDR", db=db, user=ADMIN)
    assert filtered["total_items"] == 1
    assert filtered["items"][0]["available_balance"] == Decimal("15")
