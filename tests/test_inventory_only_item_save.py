from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1.products import _normalize_item_coa, _validate_coa_mappings, _validate_treatment


def item(cogs=None):
    return SimpleNamespace(code="STOCK-1", item_type="BUY", inventory_treatment="STOCK",
                           inventory_account_id=1, purchase_account_id=None,
                           cogs_account_id=cogs, asset_account_id=None)


class Db:
    def __init__(self):
        self.lookups = []
    def get(self, model, id):
        self.lookups.append(id)
        if id == 1:
            return SimpleNamespace(id=1, account_type="ASSET", normal_balance="DEBIT",
                                   account_subtype="INVENTORY", is_active=True, is_posting=True)
        return None


@pytest.mark.parametrize("existing_cogs", [None, 999])
def test_inventory_only_save_does_not_require_or_validate_existing_cogs(existing_cogs):
    db = Db()
    record = item(existing_cogs)
    payload = {"inventory_account_id": 1, "inventory_treatment": "STOCK"}
    _normalize_item_coa(payload, record)
    _validate_treatment(payload, record)
    _validate_coa_mappings(db, payload, record)
    assert db.lookups == [1]
    assert record.cogs_account_id == existing_cogs


def test_unchanged_cogs_sent_by_older_ui_does_not_block_inventory_save():
    db = Db()
    record = item(999)
    payload = {"inventory_account_id": 1, "cogs_account_id": 999}
    _validate_coa_mappings(db, payload, record)
    assert db.lookups == [1]


def test_explicitly_changed_out_mapping_must_still_be_valid():
    db = Db()
    with pytest.raises(HTTPException):
        _validate_coa_mappings(db, {"inventory_account_id": 1, "cogs_account_id": 888}, item(999))
    assert db.lookups == [1, 888]


def test_new_stock_item_can_save_inventory_without_cogs():
    db = Db()
    payload = {"code": "NEW-1", "inventory_treatment": "STOCK", "inventory_account_id": 1}
    _normalize_item_coa(payload)
    _validate_treatment(payload)
    _validate_coa_mappings(db, payload)
    assert db.lookups == [1]
