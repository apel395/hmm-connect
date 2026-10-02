from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1.products import _validate_sales_profile, _validate_treatment
from app.models.business_unit import BusinessUnit
from app.models.location import Location


class FakeDb:
    def get(self, model, identifier):
        if model is BusinessUnit:
            return SimpleNamespace(id=identifier, is_active=True)
        if model is Location:
            return SimpleNamespace(id=identifier, is_active=True, business_unit_id=2)
        return None


def test_sell_item_pbjt_and_ppn_are_exclusive():
    with pytest.raises(HTTPException) as exc:
        _validate_sales_profile(FakeDb(), {"pbjt_rate": Decimal("10"), "sales_ppn_rate": Decimal("11")})
    assert exc.value.status_code == 422


def test_sell_item_location_must_match_business_unit():
    with pytest.raises(HTTPException) as exc:
        _validate_sales_profile(FakeDb(), {"sales_business_unit_id": 3, "sales_location_id": 4})
    assert exc.value.status_code == 422


def test_sell_service_has_no_purchase_expense_requirement():
    _validate_treatment({"item_type": "SELL", "inventory_treatment": "NON_STOCK"})
    with pytest.raises(HTTPException):
        _validate_treatment({"item_type": "BUY", "inventory_treatment": "NON_STOCK"})
