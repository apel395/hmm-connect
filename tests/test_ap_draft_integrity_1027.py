from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.goods_receipt import GoodsReceipt
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.supplier import Supplier
from app.models.supplier_invoice import SupplierInvoice, SupplierInvoiceLine
from app.schemas.supplier_invoice import SupplierInvoiceInput
from app.services.supplier_invoice_service import SupplierInvoiceService
from test_finance_delivery_1007 import ADMIN, db
from test_receiving_tax_ap_confirmation import receive
from test_stock_opname_functional import stock_db


def test_system_invoice_number_when_supplier_reference_is_missing(db, monkeypatch):
    session, unit, location, department, accounts = db
    supplier = Supplier(code="SI-AUTO-NUM", name="Reference optional")
    session.add(supplier)
    session.flush()
    payload = SupplierInvoiceInput(
        supplier_id=supplier.id,
        business_unit_id=unit.id,
        location_id=location.id,
        department_id=department.id,
        invoice_date=date(2026, 10, 28),
        lines=[dict(description="Purchased item", quantity=1, unit_price=10)],
    )
    assert payload.supplier_invoice_number == ""

    from app.services import supplier_invoice_service as module
    monkeypatch.setattr(module, "next_document_number", lambda session, prefix: "INV-SYS-0001")
    monkeypatch.setattr(SupplierInvoiceService, "validate", lambda self, data, exclude_id=None, user=None: (Decimal("10"), Decimal("10")))
    monkeypatch.setattr(SupplierInvoiceService, "_check_receipt_reservations", lambda self, data, exclude_id=None: None)
    monkeypatch.setattr(module.DirectCoaService, "snapshot_invoice_line", lambda self, invoice, line: None)
    monkeypatch.setattr(module, "record_audit", lambda *args, **kwargs: None)

    service = SupplierInvoiceService(session)
    invoice = service.create(payload, ADMIN)
    assert invoice.internal_invoice_number == "INV-SYS-0001"
    assert invoice.supplier_invoice_number == "INV-SYS-0001"
    assert invoice.status == "DRAFT"

    # Clearing an auto-prepared placeholder during Finance review retains the
    # ERP number; a real vendor reference can still be supplied later.
    invoice.supplier_invoice_number = "PENDING-GR-TEST"
    service.update(invoice, payload, ADMIN)
    assert invoice.supplier_invoice_number == "INV-SYS-0001"
    payload.supplier_invoice_number = "VENDOR-REF-100"
    service.update(invoice, payload, ADMIN)
    assert invoice.supplier_invoice_number == "VENDOR-REF-100"


def test_receipt_reservation_blocks_duplicate_drafts_and_releases_void(stock_db):
    session, _, supplier, product, receipt = receive(stock_db)
    receipt.status = "POSTED"
    first = SupplierInvoice(
        internal_invoice_number="INV-DRAFT-1", supplier_invoice_number="VENDOR-A",
        supplier_id=supplier.id, invoice_date=date(2026, 10, 23),
        goods_receipt_id=receipt.id, business_unit_id=receipt.business_unit_id,
        location_id=receipt.location_id, department_id=receipt.department_id,
        subtotal=10, total_amount=10, status="DRAFT",
    )
    first.lines = [SupplierInvoiceLine(
        product_id=product.id, goods_receipt_item_id=receipt.items[0].id,
        description=product.name, quantity=1, unit_price=10, line_amount=10,
    )]
    session.add(first)
    session.commit()

    def payload(quantity):
        return SupplierInvoiceInput(
            supplier_id=supplier.id, supplier_invoice_number="VENDOR-B",
            invoice_date=date(2026, 10, 23), goods_receipt_id=receipt.id,
            business_unit_id=receipt.business_unit_id, location_id=receipt.location_id,
            department_id=receipt.department_id,
            lines=[dict(product_id=product.id, goods_receipt_item_id=receipt.items[0].id,
                        description=product.name, quantity=quantity, unit_price=10)],
        )

    service = SupplierInvoiceService(session)
    with pytest.raises(HTTPException) as exc:
        service._check_receipt_reservations(payload(1))
    assert exc.value.status_code == 409
    assert "INV-DRAFT-1" in str(exc.value.detail)
    service._check_receipt_reservations(payload(1), exclude_id=first.id)
    first.status = "VOID"
    session.commit()
    service._check_receipt_reservations(payload(1))


def test_verified_invoice_reuses_draft_journal_after_correction(db, monkeypatch):
    session, unit, location, department, accounts = db
    supplier = Supplier(code="SI-TEST", name="Invoice supplier", payable_account_id=accounts[3].id)
    session.add(supplier)
    session.flush()
    receipt = GoodsReceipt(
        receipt_number="GR-SI-TEST", received_at=datetime(2026, 1, 3, tzinfo=timezone.utc),
        supplier_id=supplier.id, location_id=location.id, business_unit_id=unit.id,
        department_id=department.id, status="POSTED", destination_type="DIRECT_USE",
    )
    session.add(receipt)
    session.flush()
    invoice = SupplierInvoice(
        internal_invoice_number="INV-SI-TEST", supplier_invoice_number="SUP-001",
        supplier_id=supplier.id, goods_receipt_id=receipt.id,
        invoice_date=date(2026, 1, 3), business_unit_id=unit.id,
        location_id=location.id, department_id=department.id,
        subtotal=10, total_amount=10, status="VERIFIED",
    )
    invoice.lines = [SupplierInvoiceLine(description="Service", quantity=1,
                                         unit_price=10, line_amount=10, account_id=accounts[1].id)]
    session.add(invoice)
    session.commit()

    from app.services import supplier_invoice_service as module
    monkeypatch.setattr(module.DirectCoaService, "receipt_uses_grni", lambda self, inv: False)
    monkeypatch.setattr(module.DirectCoaService, "snapshot_invoice_line", lambda self, inv, line: accounts[1])
    monkeypatch.setattr(module.DirectCoaService, "payable_account", lambda self, supp, loc: accounts[3])
    monkeypatch.setattr(module, "record_audit", lambda *args, **kwargs: None)

    service = SupplierInvoiceService(session)
    original = service.generate_journal(invoice, ADMIN)
    number, journal_id = original.journal_number, original.id
    from app.api.v1 import supplier_invoices as routes
    monkeypatch.setattr(routes, "is_superuser", lambda user: True)
    monkeypatch.setattr(routes, "enforce_location_access", lambda user, location_id: None)
    monkeypatch.setattr(routes, "record_audit", lambda *args, **kwargs: None)
    monkeypatch.setattr(routes, "result", lambda session, invoice, user: invoice)
    routes.admin_reopen(invoice.id, session, ADMIN)
    assert invoice.status == "DRAFT"
    assert session.get(JournalEntry, journal_id).status == "DRAFT"
    invoice.lines[0].unit_price = Decimal("12")
    invoice.lines[0].line_amount = Decimal("12")
    invoice.subtotal = Decimal("12")
    invoice.total_amount = Decimal("12")
    invoice.status = "VERIFIED"
    session.commit()
    corrected = service.generate_journal(invoice, ADMIN)

    assert corrected.id == journal_id and corrected.journal_number == number
    assert corrected.status == "DRAFT"
    assert session.query(JournalEntry).count() == 1
    assert sum(Decimal(line.debit) for line in corrected.lines) == 12
    assert sum(Decimal(line.credit) for line in corrected.lines) == 12
    assert session.query(JournalLine).count() == 2
