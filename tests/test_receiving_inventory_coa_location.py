from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services.direct_coa_service import DirectCoaService


class AccountQuery:
    def __init__(self, setting_account_id):
        self.setting_account_id = setting_account_id

    def filter(self, *_args):
        return self

    def first(self):
        if self.setting_account_id is None:
            return None
        return SimpleNamespace(account_id=self.setting_account_id)


class FakeDb:
    def __init__(self, accounts, setting_account_id):
        self.accounts = accounts
        self.setting_account_id = setting_account_id

    def get(self, _model, account_id):
        return self.accounts.get(account_id)

    def query(self, _model):
        return AccountQuery(self.setting_account_id)


def coa(account_id, number, account_type, normal_balance, subtype="OTHER"):
    return SimpleNamespace(
        id=account_id,
        is_active=True,
        is_posting=True,
        account_type=account_type,
        normal_balance=normal_balance,
        account_subtype=subtype,
        account_number=number,
    )


def product(code="ITEM-1", inventory_account_id=None, group_name="FOOD", **kwargs):
    return SimpleNamespace(
        code=code,
        inventory_account_id=inventory_account_id,
        group_code="1",
        group_name=group_name,
        subgroup_code="0",
        subgroup_name="",
        name=code,
        **kwargs,
    )


# The resolver resolves a location INVENTORY role setting through
# DirectCoaService.inventory_account(product, location_id). A location setting
# for the item's role must win over any product-level fallback.
@pytest.mark.parametrize(
    ("group_name", "role", "account_id", "account_number"),
    [
        ("FOOD", "INVENTORY_FOOD", 100, "100-300-100"),
        ("BEVERAGE", "INVENTORY_BEVERAGE", 500, "100-300-500"),
        ("MATERIAL", "INVENTORY_MATERIAL", 700, "100-300-700"),
    ],
)
def test_inventory_account_resolves_loc2_by_role(
    group_name, role, account_id, account_number
):
    # FakeDb.query answers the LOCATION_2_{role} lookup with the seeded id.
    db = FakeDb(
        {account_id: coa(account_id, account_number, "ASSET", "DEBIT", "INVENTORY")},
        setting_account_id=account_id,
    )
    service = DirectCoaService(db)
    item = product(code="1-100011", inventory_account_id=None, group_name=group_name)

    resolved = service.inventory_account(item, location_id=2)

    assert resolved.id == account_id
    assert resolved.account_number == account_number
    assert service.inventory_role(item) == role


def test_location_setting_precedes_product_fallback():
    # A location INVENTORY_FOOD setting overrides the product's own account.
    loc_account = coa(173, "100-300-106", "ASSET", "DEBIT", "INVENTORY")
    product_account = coa(999, "100-300-999", "ASSET", "DEBIT", "INVENTORY")
    db = FakeDb({173: loc_account, 999: product_account}, setting_account_id=173)
    service = DirectCoaService(db)
    item = product(code="BEEF MINCED", inventory_account_id=999)

    resolved = service.inventory_account(item, location_id=2)

    assert resolved.id == 173


def test_missing_loc2_setting_and_product_mapping_raises_409():
    # The exact regression: a WAREHOUSE receipt for an unmapped item at a
    # location with no INVENTORY role setting must fail with 409, not silently
    # produce zero stock / zero movement.
    db = FakeDb({}, setting_account_id=None)
    service = DirectCoaService(db)
    item = product(code="BEEF MINCED", inventory_account_id=None)

    with pytest.raises(HTTPException) as error:
        service.inventory_account(item, location_id=2)

    assert error.value.status_code == 409
    assert "inventory" in error.value.detail.lower()


def test_inventory_account_declined_for_bank_account():
    # An inventory account must be a debit-balance, non-cash asset. A bank
    # account, even if mapped, must be rejected.
    bank = coa(50, "100-100-101", "ASSET", "DEBIT", "BANK")
    db = FakeDb({50: bank}, setting_account_id=50)
    service = DirectCoaService(db)
    item = product(code="BEEF MINCED")

    with pytest.raises(HTTPException) as error:
        service.inventory_account(item, location_id=2)

    assert error.value.status_code == 409
