from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.market_list import MarketList
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.supplier import Supplier
from app.schemas.market_list import MarketListConvertCreate
from app.services.market_list_service import MarketListService


class FakeQuery:
    def __init__(self, row=None, rows=None):
        self.row = row
        self.rows = rows or []

    def filter(self, *_args):
        return self

    def join(self, *_args):
        return self

    def group_by(self, *_args):
        return self

    def with_for_update(self):
        return self

    def first(self):
        return self.row

    def all(self):
        return self.rows


class FakeDb:
    def __init__(self, market_list, supplier):
        self.market_list = market_list
        self.supplier = supplier
        self.added = []

    def query(self, model):
        if model is MarketList:
            return FakeQuery(row=self.market_list)
        if model is PurchaseOrderItem:
            return FakeQuery(rows=[])
        raise AssertionError(f"Unexpected query model: {model}")

    def get(self, model, _id):
        if model is Supplier:
            return self.supplier
        raise AssertionError(f"Unexpected get model: {model}")

    def add(self, row):
        self.added.append(row)

    def flush(self):
        pass

    def commit(self):
        pass

    def refresh(self, _row):
        pass


def make_market_list():
    product = SimpleNamespace(description="Carrot", uom="KG")
    item = SimpleNamespace(
        id=101,
        product_id=10,
        quantity=Decimal("10"),
        estimated_price=Decimal("5"),
        total_price=Decimal("50"),
        is_taxable=False,
        tax_rate=Decimal("0"),
        tax_amount=Decimal("0"),
        product=product,
    )
    return SimpleNamespace(
        id=1,
        ml_number="ML-001",
        status="APPROVED",
        business_unit_id=2,
        location_id=3,
        department_id=4,
        subtotal=Decimal("50"),
        tax_amount=Decimal("0"),
        total_amount=Decimal("50"),
        items=[item],
    )


def test_selected_market_list_line_creates_traceable_partial_po(monkeypatch):
    import app.services.market_list_service as module

    monkeypatch.setattr(module, "next_document_number", lambda *_args, **_kwargs: "PO-TEST")
    monkeypatch.setattr(module.AuditService, "log", lambda **_kwargs: None)

    market_list = make_market_list()
    supplier = SimpleNamespace(id=20, is_active=True)
    db = FakeDb(market_list, supplier)

    result = MarketListService.convert_to_purchase_order(
        db=db,
        market_list_id=1,
        data=MarketListConvertCreate(
            supplier_id=20,
            items=[{"market_list_item_id": 101, "quantity": Decimal("3")}],
        ),
        current_user=SimpleNamespace(id=99),
    )

    assert result.market_list_id == 1
    assert result.subtotal == Decimal("15")
    assert len(result.items) == 1
    assert result.items[0].market_list_item_id == 101
    assert result.items[0].quantity == Decimal("3")
    assert market_list.status == "APPROVED"


def test_market_list_po_source_cannot_over_allocate_line(monkeypatch):
    import app.services.market_list_service as module

    monkeypatch.setattr(module, "next_document_number", lambda *_args, **_kwargs: "PO-TEST")
    monkeypatch.setattr(module.AuditService, "log", lambda **_kwargs: None)

    market_list = make_market_list()
    supplier = SimpleNamespace(id=20, is_active=True)
    db = FakeDb(market_list, supplier)

    with pytest.raises(HTTPException) as error:
        MarketListService.convert_to_purchase_order(
            db=db,
            market_list_id=1,
            data=MarketListConvertCreate(
                supplier_id=20,
                items=[{"market_list_item_id": 101, "quantity": Decimal("11")}],
            ),
            current_user=SimpleNamespace(id=99),
        )

    assert error.value.status_code == 409
    assert "only" in error.value.detail
