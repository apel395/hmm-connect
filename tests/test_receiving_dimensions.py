from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services.goods_receipt_service import GoodsReceiptService
from app.services.purchase_order_service import PurchaseOrderService


def dimensions(business_unit_id=None, department_id=None, location_id=None):
    return SimpleNamespace(
        business_unit_id=business_unit_id,
        department_id=department_id,
        location_id=location_id,
    )


def test_po_dimensions_inherit_unique_values_across_requisitions(monkeypatch):
    monkeypatch.setattr(
        "app.services.purchase_order_service.validate_dimensions",
        lambda *_args, **_kwargs: None,
    )
    payload = dimensions(business_unit_id=999, department_id=998, location_id=997)
    requisitions = [
        dimensions(business_unit_id=1, department_id=None, location_id=3),
        dimensions(business_unit_id=1, department_id=2, location_id=3),
    ]

    assert PurchaseOrderService._resolve_dimensions(object(), payload, requisitions) == (1, 2, 3)


def test_po_dimensions_reject_conflicting_requisitions():
    payload = dimensions()
    requisitions = [
        dimensions(business_unit_id=1, department_id=2, location_id=3),
        dimensions(business_unit_id=9, department_id=2, location_id=3),
    ]

    with pytest.raises(HTTPException) as error:
        PurchaseOrderService._resolve_dimensions(object(), payload, requisitions)

    assert error.value.status_code == 409


def test_receiving_dimensions_use_po_and_repair_unique_legacy_gap():
    requisition = dimensions(business_unit_id=1, department_id=2, location_id=3)
    purchase_order = dimensions(business_unit_id=1, department_id=None, location_id=3)
    purchase_order.source_purchase_requisitions = [requisition]
    purchase_order.market_list = None

    assert GoodsReceiptService._po_dimensions(purchase_order) == (1, 3, 2)
    assert purchase_order.department_id == 2


def test_receiving_dimensions_reject_conflicting_legacy_sources():
    purchase_order = dimensions()
    purchase_order.source_purchase_requisitions = [
        dimensions(business_unit_id=1, department_id=2, location_id=3),
        dimensions(business_unit_id=9, department_id=2, location_id=3),
    ]
    purchase_order.market_list = None

    with pytest.raises(HTTPException) as error:
        GoodsReceiptService._po_dimensions(purchase_order)

    assert error.value.status_code == 409



def test_receiving_rejects_warehouse_from_another_location():
    warehouse = SimpleNamespace(id=10, location_id=2)
    db = SimpleNamespace(get=lambda _model, _id: warehouse)
    payload = SimpleNamespace(destination_type="WAREHOUSE", warehouse_id=10)

    with pytest.raises(HTTPException) as error:
        GoodsReceiptService._validate_destination(db, payload, location_id=1)

    assert error.value.status_code == 409
    assert "receiving work location" in error.value.detail


def test_receiving_accepts_warehouse_from_same_location():
    warehouse = SimpleNamespace(id=10, location_id=2)
    db = SimpleNamespace(get=lambda _model, _id: warehouse)
    payload = SimpleNamespace(destination_type="WAREHOUSE", warehouse_id=10)

    GoodsReceiptService._validate_destination(db, payload, location_id=2)
