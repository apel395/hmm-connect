from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.warehouse import Warehouse
from app.services.goods_receipt_service import GoodsReceiptService


class FakeDb:
    def __init__(self, warehouse):
        self.warehouse = warehouse

    def get(self, model, _id):
        assert model is Warehouse
        return self.warehouse


def test_receiving_warehouse_must_match_source_location():
    db = FakeDb(SimpleNamespace(id=20, location_id=8))
    data = SimpleNamespace(destination_type="WAREHOUSE", warehouse_id=20)

    with pytest.raises(HTTPException) as error:
        GoodsReceiptService._validate_destination(db, data, location_id=7)

    assert error.value.status_code == 409
    assert error.value.detail == "Warehouse must belong to the receiving work location"


def test_receiving_warehouse_requires_location_assignment():
    db = FakeDb(SimpleNamespace(id=20, location_id=None))
    data = SimpleNamespace(destination_type="WAREHOUSE", warehouse_id=20)

    with pytest.raises(HTTPException) as error:
        GoodsReceiptService._validate_destination(db, data, location_id=7)

    assert error.value.status_code == 409
    assert error.value.detail == "Warehouse must be assigned to a work location before receiving"
