from datetime import date

from app.schemas.goods_receipt import GoodsReceiptCreate, GoodsReceiptUpdate


def test_direct_receiving_draft_accepts_empty_optional_invoice_fields():
    data = GoodsReceiptCreate.model_validate({
        "supplier_id": 1, "business_unit_id": 1, "department_id": 1, "location_id": 1,
        "source_type": "LIVE",
        "items": [{"product_id": 12, "quantity": 5, "unit_cost": 21000}],
        "supplier_invoice_number": "", "supplier_invoice_date": "",
        "supplier_invoice_due_date": "", "tax_invoice_number": "",
        "tax_invoice_date": "", "supplier_document_url": "",
        "discount_amount": 0, "shipping_fee_amount": 0,
        "admin_fee_amount": 0, "other_fee_amount": 0,
    })
    assert data.supplier_invoice_date is None
    assert data.supplier_invoice_due_date is None
    assert data.tax_invoice_date is None
    assert data.items[0].unit_cost == 21000


def test_receiving_update_accepts_empty_optional_invoice_dates():
    data = GoodsReceiptUpdate.model_validate({
        "received_at": "2026-10-31T08:30:00+07:00",
        "supplier_invoice_date": "",
        "supplier_invoice_due_date": "  ",
        "tax_invoice_date": "",
        "items": [{"item_id": 25, "quantity": 1, "unit_cost": 500, "is_taxable": False}],
    })
    assert data.supplier_invoice_date is None
    assert data.supplier_invoice_due_date is None
    assert data.tax_invoice_date is None


def test_supplied_invoice_dates_stay_valid():
    data = GoodsReceiptCreate.model_validate({
        "supplier_id": 1, "business_unit_id": 1, "department_id": 1, "location_id": 1,
        "items": [{"product_id": 12, "quantity": 1, "unit_cost": 500}],
        "supplier_invoice_date": "2026-10-31",
        "supplier_invoice_due_date": "2026-11-15",
        "tax_invoice_date": "2026-10-31",
    })
    assert data.supplier_invoice_date == date(2026, 10, 31)
    assert data.supplier_invoice_due_date == date(2026, 11, 15)
    assert data.tax_invoice_date == date(2026, 10, 31)
