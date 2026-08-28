from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services.direct_coa_service import DirectCoaService


class EmptyQuery:
    def __init__(self, row=None):
        self.row = row

    def filter(self, *_args):
        return self

    def first(self):
        return self.row


class FakeDb:
    def __init__(self, accounts, setting_account_id=None):
        self.accounts = accounts
        self.setting_account_id = setting_account_id

    def get(self, _model, account_id):
        return self.accounts.get(account_id)

    def query(self, _model):
        row = (
            SimpleNamespace(account_id=self.setting_account_id)
            if self.setting_account_id is not None
            else None
        )
        return EmptyQuery(row)


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


def test_invoice_readiness_reports_supplier_payable_before_verify():
    service = DirectCoaService(FakeDb({
        1: coa(1, "ASSET", "DEBIT", "INVENTORY"),
    }))
    invoice = SimpleNamespace(
        location_id=3,
        supplier=SimpleNamespace(code="SUP-1", payable_account_id=None),
        tax_amount=0,
        goods_receipt=SimpleNamespace(destination_type="WAREHOUSE"),
        lines=[SimpleNamespace(account_id=1, product=None)],
    )

    readiness = service.supplier_invoice_readiness(invoice)

    assert readiness["is_ready"] is False
    assert readiness["blockers"][0]["code"] == "SUPPLIER_PAYABLE"


def test_invoice_readiness_accepts_complete_direct_mappings():
    service = DirectCoaService(FakeDb({
        1: coa(1, "ASSET", "DEBIT", "INVENTORY"),
        4: coa(4, "LIABILITY", "CREDIT", "ACCOUNTS_PAYABLE"),
    }))
    invoice = SimpleNamespace(
        location_id=3,
        supplier=SimpleNamespace(code="SUP-1", payable_account_id=4),
        tax_amount=0,
        goods_receipt=SimpleNamespace(destination_type="WAREHOUSE"),
        lines=[SimpleNamespace(account_id=1, product=None)],
    )

    assert service.supplier_invoice_readiness(invoice) == {
        "is_ready": True,
        "blockers": [],
    }


def test_global_payable_precedes_supplier_fallback():
    global_payable = coa(8, "LIABILITY", "CREDIT", "ACCOUNTS_PAYABLE")
    supplier_payable = coa(4, "LIABILITY", "CREDIT", "ACCOUNTS_PAYABLE")
    service = DirectCoaService(
        FakeDb(
            {4: supplier_payable, 8: global_payable},
            setting_account_id=8,
        )
    )
    supplier = SimpleNamespace(code="SUP-1", payable_account_id=4)

    assert service.payable_account(supplier, location_id=None).id == 8


@pytest.mark.parametrize(
    ("method_name", "account"),
    [
        ("grni_account", coa(9, "LIABILITY", "CREDIT", "OTHER")),
        ("purchase_discount_account", coa(10, "INCOME", "CREDIT", "OTHER")),
        (
            "withholding_tax_payable_account",
            coa(11, "LIABILITY", "CREDIT", "OTHER"),
        ),
    ],
)
def test_global_control_accounts_resolve(method_name, account):
    service = DirectCoaService(
        FakeDb({account.id: account}, setting_account_id=account.id)
    )

    assert getattr(service, method_name)().id == account.id


@pytest.mark.parametrize(
    ("field_name", "account"),
    [
        ("input_vat_account_id", coa(20, "ASSET", "DEBIT")),
        ("accounts_payable_account_id", coa(21, "LIABILITY", "CREDIT")),
        ("grni_account_id", coa(22, "LIABILITY", "CREDIT")),
        ("purchase_discount_account_id", coa(23, "INCOME", "CREDIT")),
        (
            "withholding_tax_payable_account_id",
            coa(24, "LIABILITY", "CREDIT"),
        ),
    ],
)
def test_global_setting_policy_accepts_valid_control_accounts(field_name, account):
    from app.api.v1.accounting import _validate_direct_setting_account

    _validate_direct_setting_account(field_name, account)


def test_global_setting_policy_rejects_bank_as_grni():
    from app.api.v1.accounting import _validate_direct_setting_account

    with pytest.raises(HTTPException) as error:
        _validate_direct_setting_account(
            "grni_account_id",
            coa(25, "ASSET", "DEBIT", "BANK"),
        )
    assert error.value.status_code == 422
