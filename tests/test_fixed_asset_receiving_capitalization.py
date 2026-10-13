from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.goods_receipt import GoodsReceipt
from app.services.fixed_asset_service import FixedAssetService


class FakeDb:
    def __init__(self, receipt):
        self.receipt = receipt

    def get(self, model, _id):
        assert model is GoodsReceipt
        return self.receipt


def asset():
    return SimpleNamespace(
        status="DRAFT",
        goods_receipt_id=10,
        acquisition_date=date(2026,10,1),
        accumulated_depreciation=Decimal("0"),
        residual_value=Decimal("0"),
        net_book_value=Decimal("1000000"),
        acquisition_cost=Decimal("1000000"),
        asset_account_id=200,
        asset_category_id=1,
        useful_life_months=60,
        depreciation_method="STRAIGHT_LINE",
        accumulated_depreciation_account_id=201,
        depreciation_expense_account_id=301,
        purchase_invoice_id=None,
        capitalization_date=None,
        depreciation_start_date=None,
    )


def request(create_journal):
    return SimpleNamespace(
        capitalization_date=date(2026, 10, 2),
        depreciation_start_date=date(2026, 10, 2),
        create_journal=create_journal,
        offset_account_id=300,
    )


def test_posted_receiving_cannot_create_second_asset_acquisition_journal():
    record = asset()
    service = FixedAssetService(FakeDb(SimpleNamespace(status="POSTED")))

    with pytest.raises(HTTPException) as error:
        service.capitalize(record, request(True), SimpleNamespace(id=1))

    assert error.value.status_code == 409
    assert record.status == "DRAFT"
    assert record.capitalization_date is None


def test_posted_receiving_can_activate_asset_without_second_journal(monkeypatch):
    from app.services.fiscal_period_service import FiscalPeriodService
    monkeypatch.setattr(FiscalPeriodService,"validate_posting_date",lambda **kwargs: None)
    record = asset()
    service = FixedAssetService(FakeDb(SimpleNamespace(status="POSTED")))
    service.generate_schedule = lambda _asset: []
    service.validate_accounts = lambda _asset: None

    result = service.capitalize(record, request(False), SimpleNamespace(id=1))

    assert result.status == "ACTIVE"
    assert result.capitalization_date == date(2026, 10, 2)
