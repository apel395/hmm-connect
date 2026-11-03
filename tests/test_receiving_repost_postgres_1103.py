"""Repost placeholders must respect the production PostgreSQL uniqueness index."""
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import text

from app.models.goods_receipt import GoodsReceipt
from app.models.supplier import Supplier
from app.models.supplier_invoice import SupplierInvoice
from app.services.supplier_invoice_service import SupplierInvoiceService
from test_journal_postgres_concurrency_1028 import pg, TEST_URL

pytestmark = pytest.mark.skipif(not TEST_URL, reason="Dedicated PostgreSQL test database not configured")


def test_void_invoice_keeps_number_while_reposts_get_new_placeholders(pg):
    with pg.factory() as db:
        # Model metadata deliberately lacks the historical migration's index.
        db.execute(text("""
            CREATE UNIQUE INDEX uq_supplier_invoice_supplier_number_ci
            ON supplier_invoices (supplier_id, lower(btrim(supplier_invoice_number)))
        """))
        supplier = Supplier(code="REPOST-PG", name="Repost PostgreSQL test")
        db.add(supplier)
        db.flush()
        receipt = GoodsReceipt(
            receipt_number="GR-REPOST-PG-1", status="DRAFT", supplier_id=supplier.id,
            received_at=datetime(2026, 11, 3, tzinfo=timezone.utc),
        )
        db.add(receipt)
        db.flush()
        base = f"PENDING-{receipt.receipt_number}"

        def invoice(number, status):
            return SupplierInvoice(
                internal_invoice_number=f"INV-PG-{number[-2:]}",
                supplier_invoice_number=number,
                supplier_id=supplier.id,
                goods_receipt_id=receipt.id,
                invoice_date=date(2026, 11, 3),
                subtotal=10, total_amount=10, status=status,
            )

        original = invoice(base, "VOID")
        db.add(original)
        db.commit()

        service = SupplierInvoiceService(db)
        second_number = service._next_receipt_placeholder(receipt, supplier.id)
        assert second_number == f"{base}-R2"
        assert service._is_receipt_placeholder(receipt, second_number)
        second = invoice(second_number, "DRAFT")
        db.add(second)
        db.commit()

        second.status = "VOID"
        db.commit()
        third_number = service._next_receipt_placeholder(receipt, supplier.id)
        assert third_number == f"{base}-R3"
        db.add(invoice(third_number, "DRAFT"))
        db.commit()

        assert [item.supplier_invoice_number for item in db.query(SupplierInvoice).order_by(SupplierInvoice.id)] == [
            base, second_number, third_number,
        ]
