from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services.accounting_posting_rule_service import AccountingPostingRuleService


def coa(account_type, normal_balance, account_subtype="OTHER", account_number=""):
    return SimpleNamespace(
        account_type=account_type,
        normal_balance=normal_balance,
        account_subtype=account_subtype,
        account_number=account_number,
    )


def test_inventory_invoice_rejects_bank_as_inventory_control():
    with pytest.raises(HTTPException) as error:
        AccountingPostingRuleService._validate_event_accounts(
            "SUPPLIER_INVOICE_INVENTORY",
            coa("ASSET", "DEBIT", "BANK"),
            coa("LIABILITY", "CREDIT"),
        )
    assert error.value.status_code == 400
    assert "cash or bank" in error.value.detail


def test_supplier_invoice_requires_liability_credit():
    with pytest.raises(HTTPException):
        AccountingPostingRuleService._validate_event_accounts(
            "SUPPLIER_INVOICE_INVENTORY",
            coa("ASSET", "DEBIT", "INVENTORY"),
            coa("ASSET", "DEBIT", "BANK"),
        )


def test_direct_use_requires_expense_debit():
    with pytest.raises(HTTPException):
        AccountingPostingRuleService._validate_event_accounts(
            "SUPPLIER_INVOICE_DIRECT_USE",
            coa("ASSET", "DEBIT", "BANK"),
            coa("LIABILITY", "CREDIT"),
        )


def test_valid_supplier_invoice_controls_are_accepted():
    AccountingPostingRuleService._validate_event_accounts(
        "SUPPLIER_INVOICE_INVENTORY",
        coa("ASSET", "DEBIT", "INVENTORY"),
        coa("LIABILITY", "CREDIT"),
    )
    AccountingPostingRuleService._validate_event_accounts(
        "SUPPLIER_INVOICE_DIRECT_USE",
        coa("EXPENSE", "DEBIT"),
        coa("LIABILITY", "CREDIT"),
    )


def test_supplier_payment_requires_payable_debit_and_bank_credit():
    AccountingPostingRuleService._validate_event_accounts(
        "SUPPLIER_PAYMENT",
        coa("LIABILITY", "CREDIT", "ACCOUNTS_PAYABLE"),
        coa("ASSET", "DEBIT", "BANK"),
    )


def test_supplier_payment_rejects_bank_debit():
    with pytest.raises(HTTPException) as error:
        AccountingPostingRuleService._validate_event_accounts(
            "SUPPLIER_PAYMENT",
            coa("ASSET", "DEBIT", "BANK"),
            coa("ASSET", "DEBIT", "BANK"),
        )
    assert "payable liability" in error.value.detail


def test_source_payment_journal_rejects_legacy_bank_debit():
    with pytest.raises(HTTPException) as error:
        AccountingPostingRuleService.validate_source_journal_accounts(
            "SUPPLIER_PAYMENT",
            [coa("ASSET", "DEBIT", "BANK")],
            [coa("ASSET", "DEBIT", "BANK")],
        )
    assert error.value.status_code == 409


def test_source_invoice_journal_rejects_bank_control_accounts():
    with pytest.raises(HTTPException):
        AccountingPostingRuleService.validate_source_journal_accounts(
            "SUPPLIER_INVOICE",
            [coa("ASSET", "DEBIT", "BANK")],
            [coa("LIABILITY", "CREDIT", "ACCOUNTS_PAYABLE")],
        )
    with pytest.raises(HTTPException):
        AccountingPostingRuleService.validate_source_journal_accounts(
            "SUPPLIER_INVOICE",
            [coa("ASSET", "DEBIT", "INVENTORY")],
            [coa("ASSET", "DEBIT", "BANK")],
        )


def test_direct_use_accepts_only_approved_inventory_asset_fallback():
    AccountingPostingRuleService._validate_event_accounts(
        "SUPPLIER_INVOICE_DIRECT_USE",
        coa("ASSET", "DEBIT", "INVENTORY", "100-300-999"),
        coa("LIABILITY", "CREDIT"),
    )


@pytest.mark.parametrize("account_number", ["100-300-100", "100-110-119", ""])
def test_direct_use_rejects_unapproved_asset_fallback(account_number):
    with pytest.raises(HTTPException) as error:
        AccountingPostingRuleService._validate_event_accounts(
            "SUPPLIER_INVOICE_DIRECT_USE",
            coa("ASSET", "DEBIT", "INVENTORY", account_number),
            coa("LIABILITY", "CREDIT"),
        )
    assert "approved temporary inventory fallback" in error.value.detail


@pytest.mark.parametrize(
    ("subtype", "account_number"),
    [
        ("ACCOUNTS_RECEIVABLE", "100-999-001"),
        ("OTHER", "100-200-103"),
    ],
)
def test_supplier_invoice_rejects_receivable_line_accounts(subtype, account_number):
    with pytest.raises(HTTPException) as error:
        AccountingPostingRuleService.validate_invoice_debit_account(
            "SUPPLIER_INVOICE_INVENTORY",
            coa("ASSET", "DEBIT", subtype, account_number),
        )
    assert error.value.status_code == 409
    assert "accounts receivable" in error.value.detail


def test_supplier_invoice_accepts_valid_scoped_default_account():
    AccountingPostingRuleService.validate_invoice_debit_account(
        "SUPPLIER_INVOICE_INVENTORY",
        coa("ASSET", "DEBIT", "INVENTORY", "100-300-100"),
    )


def test_supplier_invoice_accepts_only_configured_grni_liability_debit():
    grni = coa("LIABILITY", "CREDIT")
    grni.id = 77
    payable = coa("LIABILITY", "CREDIT")
    payable.id = 88

    with pytest.raises(HTTPException):
        AccountingPostingRuleService.validate_source_journal_accounts(
            "SUPPLIER_INVOICE",
            [grni],
            [payable],
        )

    AccountingPostingRuleService.validate_source_journal_accounts(
        "SUPPLIER_INVOICE",
        [grni],
        [payable],
        allowed_liability_debit_ids={77},
    )


def test_supplier_invoice_accepts_discount_and_withholding_credits():
    expense = coa("EXPENSE", "DEBIT")
    expense.id = 1
    payable = coa("LIABILITY", "CREDIT")
    payable.id = 2
    withholding = coa("LIABILITY", "CREDIT")
    withholding.id = 3
    discount = coa("INCOME", "CREDIT")
    discount.id = 4

    AccountingPostingRuleService.validate_source_journal_accounts(
        "SUPPLIER_INVOICE",
        [expense],
        [payable, withholding, discount],
    )


def test_legacy_posting_rules_are_read_only():
    from app.api.v1.accounting_posting_rules import ensure_legacy_read_only

    with pytest.raises(HTTPException) as error:
        ensure_legacy_read_only()

    assert error.value.status_code == 409
    assert error.value.detail["code"] == "POSTING_RULES_READ_ONLY"


def test_posting_rule_reads_remain_available_while_mutations_are_frozen():
    import inspect

    from app.api.v1.accounting_posting_rules import (
        create_rule,
        get_rule,
        list_rules,
        toggle,
        update_rule,
    )

    assert "ensure_legacy_read_only" not in inspect.getsource(list_rules)
    assert "ensure_legacy_read_only" not in inspect.getsource(get_rule)
    assert "ensure_legacy_read_only" in inspect.getsource(create_rule)
    assert "ensure_legacy_read_only" in inspect.getsource(update_rule)
    assert "ensure_legacy_read_only" in inspect.getsource(toggle)
