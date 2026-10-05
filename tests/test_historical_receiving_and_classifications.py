from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1 import goods_receipts as api
from app.api.v1.products import classification_catalog
from app.services.goods_receipt_service import GoodsReceiptService
from app.services.fiscal_period_service import FiscalPeriodService


def test_classification_includes_all_existing_groups_and_missing_subgroups():
    groups = [SimpleNamespace(id=1, code='1', name='FOOD', item_type='BUY', is_active=True,
                              subgroups=[SimpleNamespace(id=1, code='1-1', name='MEAT', is_active=True)])]
    products = [('BUY', '1', 'OLD FOOD', '1-2', 'VEGETABLES'),
                ('BUY', '2', 'BEVERAGE', '2-1', 'SOFT DRINK'),
                ('BUY', '4', 'ASSET', '4-2', 'FURNITURE')]
    result = classification_catalog(groups, products, 'BUY')
    assert [row['code'] for row in result] == ['1', '2', '4']
    assert result[0]['name'] == 'FOOD'
    assert [row['name'] for row in result[0]['subgroups']] == ['MEAT', 'VEGETABLES']
    assert products[0][2] == 'OLD FOOD'  # Read-only recovery, no master rewrite.


def test_classification_keeps_buy_sell_separate_and_inactive_choices_hidden():
    groups = [SimpleNamespace(id=1, code='9', name='Retired', item_type='BUY', is_active=False, subgroups=[]),
              SimpleNamespace(id=2, code='1', name='FOOD', item_type='BUY', is_active=True,
                              subgroups=[SimpleNamespace(id=3, code='1-9', name='Retired', is_active=False)])]
    products = [('BUY', '9', 'Retired', '9-1', 'Old'), ('BUY', '1', 'FOOD', '1-9', 'Retired'),
                ('SELL', '1', 'RESTAURANT', '1-1', 'Menu')]
    buy = classification_catalog(groups, products, 'BUY')
    sell = classification_catalog(groups, products, 'SELL')
    assert len(buy) == 1 and buy[0]['subgroups'] == []
    assert sell[0]['name'] == 'RESTAURANT'


@pytest.fixture
def historical_policy(monkeypatch):
    monkeypatch.setattr(GoodsReceiptService, '_check_access', lambda user, permission: None)
    monkeypatch.setattr(FiscalPeriodService, 'business_today', lambda: date(2026, 10, 5))
    monkeypatch.setattr(FiscalPeriodService, 'validate_posting_date', lambda db, day: SimpleNamespace(is_open=True))


def test_historical_receiving_uses_period_policy(historical_policy, monkeypatch):
    checked = []
    monkeypatch.setattr(FiscalPeriodService, 'validate_posting_date', lambda db, day: checked.append(day) or object())
    GoodsReceiptService.check_historical_entry(object(), datetime(2026, 1, 31, tzinfo=timezone.utc), object())
    assert checked == [date(2026, 1, 31)]


@pytest.mark.parametrize('received_at', [None, datetime(2025, 12, 31), datetime(2026, 10, 5), datetime(2026, 10, 6)])
def test_historical_receiving_requires_a_past_2026_date(historical_policy, received_at):
    with pytest.raises(HTTPException) as error:
        GoodsReceiptService.check_historical_entry(object(), received_at, object())
    assert error.value.status_code == 422


def test_historical_receiving_respects_closed_or_disabled_backdate_period(historical_policy, monkeypatch):
    def blocked(db, day):
        raise HTTPException(400, 'Period closed or backdating disabled')
    monkeypatch.setattr(FiscalPeriodService, 'validate_posting_date', blocked)
    with pytest.raises(HTTPException) as error:
        GoodsReceiptService.check_historical_entry(object(), datetime(2026, 1, 31), object())
    assert error.value.status_code == 400


def test_historical_receiving_requires_post_permission(historical_policy, monkeypatch):
    def denied(user, permission):
        assert permission == 'receiving.post'
        raise HTTPException(403, 'Permission required')
    monkeypatch.setattr(GoodsReceiptService, '_check_access', denied)
    with pytest.raises(HTTPException) as error:
        GoodsReceiptService.check_historical_entry(object(), datetime(2026, 1, 31), object())
    assert error.value.status_code == 403


@pytest.mark.parametrize('source_type,approval,allowed', [
    ('LIVE', None, False), ('LIVE', SimpleNamespace(status='APPROVED'), True),
    ('HISTORICAL_ENTRY', None, True), ('HISTORICAL_ENTRY', SimpleNamespace(status='REJECTED'), False),
    ('HISTORICAL_IMPORT', None, False),
])
def test_post_bypass_only_for_explicit_historical_entry(monkeypatch, source_type, approval, allowed):
    receipt = SimpleNamespace(id=1, source_type=source_type)
    monkeypatch.setattr(api, '_scoped_receipt_for_update', lambda db, id, user: receipt)
    monkeypatch.setattr(api, 'get_request', lambda *args: approval)
    monkeypatch.setattr(GoodsReceiptService, 'post', lambda **kwargs: receipt)
    monkeypatch.setattr(api, 'serialize_receipt', lambda receipt, db: receipt)
    if allowed:
        assert api.post_receipt(1, object(), object()) is receipt
    else:
        with pytest.raises(HTTPException) as error:
            api.post_receipt(1, object(), object())
        assert error.value.status_code == 409
