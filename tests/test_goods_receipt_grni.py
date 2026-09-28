from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.journal_entry import JournalEntry
from app.services.goods_receipt_service import GoodsReceiptService


class FakeQuery:
    def __init__(self, row=None):
        self.row = row

    def filter(self, *_args):
        return self

    def order_by(self, *_args):
        return self

    def first(self):
        return self.row


class FakeDb:
    def __init__(self, existing=None):
        self.existing = existing
        self.added = []

    def query(self, _model):
        return FakeQuery(self.existing)

    def add(self, row):
        self.added.append(row)


class Resolver:
    def __init__(self, _db):
        pass

    def ap_suspense_account(self):
        return SimpleNamespace(id=90)

    def inventory_account(self, product, _location_id):
        return SimpleNamespace(id=product.inventory_account_id)


def receipt():
    return SimpleNamespace(
        id=7,
        receipt_number="GR-TEST",
        destination_type="WAREHOUSE",
        received_at=datetime(2026, 8, 28, tzinfo=timezone.utc),
        business_unit_id=2,
        location_id=3,
        department_id=4,
        supplier_id=5,
        subtotal=Decimal("350.00"),
        items=[
            SimpleNamespace(
                product=SimpleNamespace(code="ITEM-10", inventory_treatment="STOCK", inventory_account_id=10),
                quantity=Decimal("2"),
                unit_cost=Decimal("100"),
            ),
            SimpleNamespace(
                product=SimpleNamespace(code="ITEM-11", inventory_treatment="STOCK", inventory_account_id=11),
                quantity=Decimal("3"),
                unit_cost=Decimal("50"),
            ),
        ],
    )


def test_warehouse_receipt_generates_balanced_inventory_grni_journal(monkeypatch):
    import app.services.goods_receipt_service as module

    monkeypatch.setattr(module, "DirectCoaService", Resolver)
    monkeypatch.setattr(module, "next_document_number", lambda *_args, **_kwargs: "JV-TEST")
    db = FakeDb()

    journal = GoodsReceiptService._sync_accounting_journal(
        db,
        receipt=receipt(),
        user=SimpleNamespace(id=99),
    )

    assert journal.reference_type == "GOODS_RECEIPT"
    assert journal.status == "DRAFT"
    assert [line.account_id for line in journal.lines] == [10, 11, 90]
    assert sum(Decimal(line.debit) for line in journal.lines) == Decimal("350.00")
    assert sum(Decimal(line.credit) for line in journal.lines) == Decimal("350.00")
    assert all(line.location_id == 3 for line in journal.lines)


def test_posted_receipt_journal_must_be_unposted_before_cost_resync(monkeypatch):
    import app.services.goods_receipt_service as module

    monkeypatch.setattr(module, "DirectCoaService", Resolver)
    existing = SimpleNamespace(status="POSTED", journal_number="GR-0001")
    db = FakeDb(existing=existing)

    with pytest.raises(HTTPException) as error:
        GoodsReceiptService._sync_accounting_journal(
            db,
            receipt=receipt(),
            user=SimpleNamespace(id=99),
        )

    assert error.value.status_code == 409
    assert "Unpost" in error.value.detail


def test_receipt_return_guards_accounting_journal_lifecycle():
    import inspect

    source = inspect.getsource(GoodsReceiptService.return_receipt)
    assert 'accounting_journal.status == "POSTED"' in source
    assert 'accounting_journal.status = "VOID"' in source
