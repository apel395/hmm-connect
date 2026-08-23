from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services.accounting_posting_rule_service import AccountingPostingRuleService


def coa(account_type, normal_balance, account_subtype="OTHER"):
    return SimpleNamespace(
        account_type=account_type,
        normal_balance=normal_balance,
        account_subtype=account_subtype,
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
