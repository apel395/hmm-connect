from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1.products import _normalize_item_coa, _validate_treatment


def test_direct_use_clears_unrelated_mappings_and_requires_only_expense():
    product = SimpleNamespace(inventory_treatment="STOCK", inventory_account_id=99, purchase_account_id=None, asset_account_id=None, item_type="BUY")
    payload = {"inventory_treatment": "DIRECT_USE", "purchase_account_id": 20, "cogs_account_id": 99}
    _normalize_item_coa(payload, product)
    _validate_treatment(payload, product)
    assert payload["purchase_account_id"] == 20
    assert all(payload[field] is None for field in ("inventory_account_id", "asset_account_id", "cogs_account_id"))


def test_stock_requires_inventory_but_not_issue_expense():
    payload = {"inventory_treatment": "STOCK", "inventory_account_id": 10}
    _normalize_item_coa(payload)
    _validate_treatment(payload)
    assert "cogs_account_id" not in payload


@pytest.mark.parametrize("treatment,account", [("DIRECT_USE", "purchase_account_id"), ("NON_STOCK", "purchase_account_id"), ("FIXED_ASSET", "asset_account_id")])
def test_only_primary_account_is_needed(treatment, account):
    payload = {"inventory_treatment": treatment, account: 10}
    _normalize_item_coa(payload)
    _validate_treatment(payload)
    assert payload[account] == 10
    assert payload["cogs_account_id"] is None


def test_missing_direct_use_expense_remains_a_real_error():
    payload = {"inventory_treatment": "DIRECT_USE", "inventory_account_id": 10}
    _normalize_item_coa(payload)
    with pytest.raises(HTTPException):
        _validate_treatment(payload)


def test_name_only_edit_does_not_change_existing_mapping_or_tax():
    payload = {"name": "Corrected item"}
    _normalize_item_coa(payload, SimpleNamespace(inventory_treatment="STOCK"))
    assert payload == {"name": "Corrected item"}


def test_rule_never_invents_a_tax_rate_or_balance():
    payload = {"inventory_treatment": "DIRECT_USE", "purchase_account_id": 20}
    _normalize_item_coa(payload)
    assert not {"tax_rate", "is_taxable", "opening_balance", "balance", "journal_entry_id"}.intersection(payload)
