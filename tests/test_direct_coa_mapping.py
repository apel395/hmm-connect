from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services.direct_coa_service import DirectCoaService


class FakeDb:
    def __init__(self, accounts):
        self.accounts = accounts

    def get(self, _model, account_id):
        return self.accounts.get(account_id)


def coa(account_id, account_type, normal_balance, subtype="OTHER", number=""):
    return SimpleNamespace(
        id=account_id,
        is_active=True,
        is_posting=True,
        account_type=account_type,
        normal_balance=normal_balance,
        account_subtype=subtype,
        account_number=number,
    )


def product(**kwargs):
    defaults = {
        "code": "ITEM-1",
        "inventory_account_id": 1,
        "purchase_account_id": 2,
        "cogs_account_id": 3,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_product_direct_mappings_resolve_without_posting_rule():
    service = DirectCoaService(FakeDb({
        1: coa(1, "ASSET", "DEBIT", "INVENTORY"),
        2: coa(2, "EXPENSE", "DEBIT"),
        3: coa(3, "EXPENSE", "DEBIT"),
    }))
    assert service.inventory_account(product()).id == 1
    assert service.expense_account(product()).id == 2
    assert service.cogs_account(product()).id == 3


def test_missing_item_mapping_fails_before_journal_creation():
    service = DirectCoaService(FakeDb({}))
    with pytest.raises(HTTPException) as error:
        service.inventory_account(product(inventory_account_id=None))
    assert error.value.status_code == 409
    assert "inventory" in error.value.detail


def test_supplier_payable_must_be_credit_balance_liability():
    service = DirectCoaService(FakeDb({4: coa(4, "ASSET", "DEBIT", "BANK")}))
    supplier = SimpleNamespace(code="SUP-1", payable_account_id=4)
    with pytest.raises(HTTPException) as error:
        service.payable_account(supplier)
    assert "liability" in error.value.detail


def test_invoice_rejects_receivable_even_when_explicitly_selected():
    service = DirectCoaService(FakeDb({}))
    with pytest.raises(HTTPException) as error:
        service.validate_invoice_debit(
            coa(5, "ASSET", "DEBIT", "ACCOUNTS_RECEIVABLE", "100-200-100"),
            inventory=True,
        )
    assert "receivable" in error.value.detail
