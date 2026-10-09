from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import app.services.stock_opname_service as stock_opname_service
from app.models.location import Location
from app.models.stock_opname import StockOpnameItem
from app.schemas.stock_opname import StockOpnameCreate
from app.services.stock_opname_service import StockOpnameService


def test_stock_opname_variance_math():
    item = StockOpnameItem(
        product_id=1,
        system_quantity=Decimal("20"),
        physical_quantity=Decimal("17"),
        unit_cost=Decimal("10"),
        uom="PCS",
    )
    item.variance_quantity = item.physical_quantity - item.system_quantity
    assert item.variance_quantity == Decimal("-3")


def test_stock_opname_positive_variance_math():
    item = StockOpnameItem(
        product_id=1,
        system_quantity=Decimal("20"),
        physical_quantity=Decimal("24"),
        unit_cost=Decimal("10"),
        uom="PCS",
    )
    item.variance_quantity = item.physical_quantity - item.system_quantity
    assert item.variance_quantity == Decimal("4")


def test_stock_opname_derives_business_unit_from_selected_location(monkeypatch):
    location = SimpleNamespace(id=7, is_active=True, business_unit_id=3)

    class FakeDb:
        def get(self, model, record_id):
            if model is Location and record_id == 7:
                return location
            return None

    validated = {}

    def fake_validate(db, business_unit_id, location_id, department_id, required):
        validated.update(
            business_unit_id=business_unit_id,
            location_id=location_id,
            department_id=department_id,
            required=required,
        )

    monkeypatch.setattr(stock_opname_service, "validate_dimensions", fake_validate)
    user = SimpleNamespace(
        default_business_unit_id=None,
        default_location_id=None,
        location_id=None,
        default_department_id=None,
        department_id=None,
    )
    data = StockOpnameCreate(warehouse_id=1, location_id=7, department_id=8)

    result = StockOpnameService._resolve_dimensions(
        FakeDb(), data=data, current_user=user
    )

    assert result == (3, 7, 8)
    assert validated == {
        "business_unit_id": 3,
        "location_id": 7,
        "department_id": 8,
        "required": True,
    }


def test_stock_opname_requires_location_when_user_has_no_default():
    class FakeDb:
        def get(self, model, record_id):
            return None

    user = SimpleNamespace(
        default_business_unit_id=None,
        default_location_id=None,
        location_id=None,
        default_department_id=None,
        department_id=None,
    )
    data = StockOpnameCreate(warehouse_id=1)

    with pytest.raises(HTTPException) as exc:
        StockOpnameService._resolve_dimensions(
            FakeDb(), data=data, current_user=user
        )

    assert exc.value.status_code == 422
    assert exc.value.detail == "Location is required for Stock Opname"
