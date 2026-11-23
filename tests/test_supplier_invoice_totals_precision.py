"""Supplier invoice totals must agree at currency precision (Numeric(18,2))."""
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.supplier import Supplier
from app.schemas.supplier_invoice import SupplierInvoiceInput
from app.services.supplier_invoice_service import SupplierInvoiceService


def payload(document_total):
    return {
        "supplier_id": 1,
        "business_unit_id": 1,
        "department_id": 1,
        "location_id": 1,
        "invoice_date": "2026-11-23",
        "supplier_document_total": Decimal(document_total),
        "lines": [{
            "description": "Sub-cent PPN case",
            "quantity": Decimal("3"),
            "unit_price": Decimal("1234.56"),
            "is_taxable": True,
            "tax_rate": Decimal("11"),
        }],
    }


class FakeDb:
    def get(self, model, key):
        return SimpleNamespace(id=key) if model is Supplier else None


def test_line_tax_and_total_are_quantized_like_stored_currency():
    data = SupplierInvoiceInput(**payload("4111.08"))

    assert data.tax_amount == Decimal("407.40")   # raw 407.4048
    assert data.total_amount == Decimal("4111.08")  # raw 4111.0848
    assert data.supplier_document_total == Decimal("4111.08")


def test_matching_document_total_validates(monkeypatch):
    monkeypatch.setattr("app.services.organization_dimensions.validate_dimensions", lambda *a, **k: None)
    data = SupplierInvoiceInput(**payload("4111.08"))

    subtotal, total = SupplierInvoiceService(FakeDb()).validate(data)

    assert subtotal == Decimal("3703.68")
    assert total == Decimal("4111.08")


def test_wrong_document_total_still_rejects_with_field_metadata(monkeypatch):
    monkeypatch.setattr("app.services.organization_dimensions.validate_dimensions", lambda *a, **k: None)
    data = SupplierInvoiceInput(**payload("4111.07"))

    with pytest.raises(HTTPException) as raised:
        SupplierInvoiceService(FakeDb()).validate(data)

    detail = raised.value.detail
    assert raised.value.status_code == 422
    assert detail["message"] == "Invoice charges and taxes do not match the supplier document total"
    assert detail["code"] == "SUPPLIER_DOCUMENT_TOTAL_MISMATCH"
    assert detail["fields"][0]["path"] == "supplier_document_total"
    assert detail["fields"][0]["actual"] == "4111.07"
    assert detail["fields"][0]["expected"] == "4111.08"
    assert detail["totals"]["calculated_total"] == "4111.08"
