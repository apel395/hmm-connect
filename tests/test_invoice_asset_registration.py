from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.fixed_asset import FixedAsset, FixedAssetCategory, FixedAssetMovement
from app.models.supplier_invoice import SupplierInvoice
from app.services import invoice_asset_registration as registration


class Query:
    def __init__(self, db, model):
        self.db, self.model = db, model

    def filter(self, *args):
        return self

    def with_for_update(self):
        return self

    def limit(self, count):
        return self

    def one(self):
        return (self.db.invoice.id,)

    def one_or_none(self):
        return self.db.asset

    def all(self):
        return []


class Db:
    def __init__(self, invoice):
        self.invoice = invoice
        self.asset = None
        self.movements = []

    def query(self, model):
        return Query(self, model)

    def get(self, model, ident):
        return SimpleNamespace(business_unit_id=1)

    def add(self, item):
        if isinstance(item, FixedAsset):
            self.asset = item
        elif isinstance(item, FixedAssetMovement):
            self.movements.append(item)

    def flush(self):
        if self.asset and self.asset.id is None:
            self.asset.id = 1


def test_posted_invoice_reclassification_registers_once_without_new_journal(monkeypatch):
    invoice = SimpleNamespace(
        id=611, status="POSTED", goods_receipt_id=None,
        business_unit_id=1, location_id=1, department_id=None,
        supplier_id=9, purchase_order_id=None, invoice_date=date(2026, 1, 8),
        internal_invoice_number="INV-611",
    )
    line = SimpleNamespace(
        id=900, goods_receipt_item_id=None, line_amount=Decimal("5500000.00"),
        product=None, description="Computer", department_id=None,
    )
    journal = SimpleNamespace(id=1349, status="POSTED", location_id=1, business_unit_id=1)
    db = Db(invoice)
    monkeypatch.setattr(registration, "next_document_number", lambda db, prefix: "FA-TEST-1")
    monkeypatch.setattr(registration, "record_audit", lambda *args, **kwargs: None)

    first = registration.register_invoice_asset(
        db, invoice=invoice, line=line, account_id=104, journal=journal,
        user=SimpleNamespace(id=45),
    )
    second = registration.register_invoice_asset(
        db, invoice=invoice, line=line, account_id=104, journal=journal,
        user=SimpleNamespace(id=45),
    )

    assert first is second
    assert first.status == "PENDING_SETUP"
    assert first.acquisition_cost == Decimal("5500000.00")
    assert first.purchase_invoice_id == 611
    assert first.source_invoice_line_id == 900
    assert len(db.movements) == 1


def test_unposted_correction_cannot_restore_source_asset(monkeypatch):
    invoice = SimpleNamespace(id=611, status="POSTED")
    db = Db(invoice)
    with pytest.raises(HTTPException) as error:
        registration.register_invoice_asset(
            db, invoice=invoice,
            line=SimpleNamespace(id=900), account_id=104,
            journal=SimpleNamespace(status="DRAFT"),
            user=SimpleNamespace(id=45),
        )
    assert error.value.status_code == 409
