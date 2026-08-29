from types import SimpleNamespace

from app.services.cash_flow_service import CashFlowService
from app.services.supplier_invoice_service import SupplierInvoiceService


def test_registered_bank_coa_is_treated_as_cash_account():
    service = CashFlowService(db=None)
    service._linked_bank_account_ids = {42}

    account = SimpleNamespace(id=42, account_subtype="OTHER")

    assert service.is_cash_account(account) is True


def test_unregistered_other_coa_is_not_treated_as_cash_account():
    service = CashFlowService(db=None)
    service._linked_bank_account_ids = {42}

    account = SimpleNamespace(id=99, account_subtype="OTHER")

    assert service.is_cash_account(account) is False


def test_supplier_invoice_serializer_falls_back_to_receipt_warehouse_location():
    location = SimpleNamespace(id=3, name="Zamped")
    receipt = SimpleNamespace(
        receipt_number="RR-TEST",
        location=None,
        warehouse=SimpleNamespace(location=location),
        purchase_order=None,
    )
    supplier = SimpleNamespace(name="Test Supplier")
    invoice = SimpleNamespace(
        id=17,
        internal_invoice_number="INV-TEST",
        supplier_invoice_number="SUP-TEST",
        supplier_id=1,
        supplier=supplier,
        invoice_date=None,
        received_date=None,
        due_date=None,
        purchase_order_id=None,
        purchase_order=None,
        goods_receipt_id=1,
        goods_receipt=receipt,
        business_unit_id=2,
        department_id=None,
        department=None,
        location_id=None,
        location=None,
        currency="IDR",
        subtotal=0,
        discount_amount=0,
        tax_amount=0,
        withholding_tax_amount=0,
        total_amount=0,
        paid_amount=0,
        balance_amount=0,
        payment_status="UNPAID",
        tax_invoice_number=None,
        tax_invoice_date=None,
        status="DRAFT",
        notes=None,
        source_type="LIVE",
        created_by=None,
        created_at=None,
        updated_at=None,
        verified_at=None,
        posted_at=None,
        voided_at=None,
        lines=[],
        _journals=[],
    )

    result = SupplierInvoiceService.serialize(invoice)

    assert result["location_id"] == 3
    assert result["location_name"] == "Zamped"


def test_supplier_invoice_serializer_falls_back_to_posted_journal_location():
    location = SimpleNamespace(id=3, name="Zamped")
    journal = SimpleNamespace(
        id=27,
        journal_number="SI-TEST",
        status="POSTED",
        reference_type="SUPPLIER_INVOICE",
        location=None,
        lines=[SimpleNamespace(location=location)],
    )
    supplier = SimpleNamespace(name="Test Supplier")
    invoice = SimpleNamespace(
        id=17,
        internal_invoice_number="INV-TEST",
        supplier_invoice_number="SUP-TEST",
        supplier_id=1,
        supplier=supplier,
        invoice_date=None,
        received_date=None,
        due_date=None,
        purchase_order_id=None,
        purchase_order=None,
        goods_receipt_id=None,
        goods_receipt=None,
        business_unit_id=2,
        department_id=None,
        department=None,
        location_id=None,
        location=None,
        currency="IDR",
        subtotal=0,
        discount_amount=0,
        tax_amount=0,
        withholding_tax_amount=0,
        total_amount=0,
        paid_amount=0,
        balance_amount=0,
        payment_status="PARTIALLY_PAID",
        tax_invoice_number=None,
        tax_invoice_date=None,
        status="POSTED",
        notes=None,
        source_type="LIVE",
        created_by=None,
        created_at=None,
        updated_at=None,
        verified_at=None,
        posted_at=None,
        voided_at=None,
        lines=[],
        _journals=[journal],
    )

    result = SupplierInvoiceService.serialize(invoice)

    assert result["location_id"] == 3
    assert result["location_name"] == "Zamped"


def test_supplier_invoice_source_location_uses_matching_warehouse_location():
    receipt = SimpleNamespace(
        destination_type="WAREHOUSE",
        location_id=3,
        warehouse=SimpleNamespace(location_id=3),
    )
    purchase_order = SimpleNamespace(location_id=3)

    assert SupplierInvoiceService._source_location_id(receipt, purchase_order) == 3


def test_supplier_invoice_source_location_rejects_warehouse_conflict():
    receipt = SimpleNamespace(
        destination_type="WAREHOUSE",
        location_id=4,
        warehouse=SimpleNamespace(location_id=3),
    )
    purchase_order = SimpleNamespace(location_id=3)

    with pytest.raises(HTTPException, match="does not match"):
        SupplierInvoiceService._source_location_id(receipt, purchase_order)


def test_supplier_invoice_source_location_uses_direct_receipt_location():
    receipt = SimpleNamespace(
        destination_type="DIRECT_USE",
        location_id=4,
        warehouse=SimpleNamespace(location_id=3),
    )

    assert SupplierInvoiceService._source_location_id(receipt, None) == 4
