#!/usr/bin/env python3
"""Audit Cash/Bank accounts and safely align finance posting rules.

Usage:
  PYTHONPATH=. python scripts/audit_finance_setup.py
  PYTHONPATH=. python scripts/audit_finance_setup.py --apply-safe

The apply mode only performs deterministic repairs:
- map Supplier Invoice input VAT to COA 100-500-100;
- align SUPPLIER_PAYMENT debit to the common AP liability used by invoice rules.
It never guesses bank-account locations or rewrites funding-account COA links.
"""

from __future__ import annotations

import argparse

from app.core.database import SessionLocal
from app.models.accounting_posting_rule import AccountingPostingRule
from app.models.bank_account import BankAccount
from app.models.chart_of_account import ChartOfAccount
from app.services.accounting_posting_rule_service import AccountingPostingRuleService

VAT_CODE = "100-500-100"
INVOICE_EVENTS = ("SUPPLIER_INVOICE_INVENTORY", "SUPPLIER_INVOICE_DIRECT_USE")
PAYMENT_EVENT = "SUPPLIER_PAYMENT"
FUNDING_SUBTYPES = {"BANK", "CASH", "PETTY_CASH", "CASH_AND_BANK"}


def account_label(account: ChartOfAccount | None) -> str:
    if not account:
        return "MISSING"
    return f"{account.account_number} — {account.account_name}"


def audit_bank_accounts(db) -> int:
    print("\n=== CASH / BANK ACCOUNTS ===")
    invalid = 0
    rows = db.query(BankAccount).order_by(BankAccount.business_unit_id, BankAccount.location_id, BankAccount.id).all()
    if not rows:
        print("No bank/cash accounts configured.")
        return 1
    for row in rows:
        coa = row.coa_account
        scope = row.location.name if row.location else "GLOBAL / ALL LOCATIONS"
        valid_coa = bool(
            coa
            and coa.is_active
            and coa.is_posting
            and coa.account_type == "ASSET"
            and str(coa.account_subtype or "").upper() in FUNDING_SUBTYPES
        )
        if not valid_coa:
            invalid += 1
        print(
            f"[{'OK' if valid_coa else 'INVALID'}] id={row.id} "
            f"{row.bank_name} — {row.account_name} — {row.account_number} | "
            f"BU={row.business_unit.name if row.business_unit else row.business_unit_id} | "
            f"Location={scope} | Currency={row.currency} | "
            f"COA={account_label(coa)} | subtype={getattr(coa, 'account_subtype', None)}"
        )
    return invalid


def active_rules(db, event: str):
    return (
        db.query(AccountingPostingRule)
        .filter(
            AccountingPostingRule.event_type == event,
            AccountingPostingRule.is_active.is_(True),
        )
        .order_by(
            AccountingPostingRule.business_unit_id.nullsfirst(),
            AccountingPostingRule.location_id.nullsfirst(),
            AccountingPostingRule.id,
        )
        .all()
    )


def rule_scope(rule: AccountingPostingRule) -> str:
    bu = rule.business_unit.name if rule.business_unit else "GLOBAL-BU"
    loc = rule.location.name if rule.location else "GLOBAL-LOCATION"
    return f"{bu} / {loc}"


def audit_rules(db) -> int:
    print("\n=== POSTING RULES ===")
    invalid = 0
    svc = AccountingPostingRuleService(db)
    for event in (*INVOICE_EVENTS, PAYMENT_EVENT):
        rows = active_rules(db, event)
        if not rows:
            print(f"[MISSING] {event}: no active rule")
            invalid += 1
            continue
        for rule in rows:
            try:
                svc.validate(
                    rule.debit_account_id,
                    rule.credit_account_id,
                    rule.event_type,
                    exclude_id=rule.id,
                    active=True,
                    input_vat_account_id=rule.input_vat_account_id,
                    business_unit_id=rule.business_unit_id,
                    location_id=rule.location_id,
                )
                status = "OK"
            except Exception as exc:
                status = f"INVALID: {getattr(exc, 'detail', str(exc))}"
                invalid += 1
            print(
                f"[{status}] id={rule.id} {event} | {rule_scope(rule)} | "
                f"DR {account_label(rule.debit_account)} | "
                f"CR {account_label(rule.credit_account)} | "
                f"VAT {account_label(rule.input_vat_account) if rule.input_vat_account_id else '-'}"
            )
    return invalid


def audit_location_candidates(db) -> None:
    print("\n=== LOCATION POSTING CANDIDATES ===")
    locations = db.execute(
        __import__("sqlalchemy").text(
            """
            SELECT l.id, l.code, l.name, bu.name AS business_unit_name
            FROM locations l
            LEFT JOIN business_units bu ON bu.id = l.business_unit_id
            WHERE l.is_active = true
            ORDER BY bu.name NULLS LAST, l.name
            """
        )
    ).mappings().all()
    accounts = db.query(ChartOfAccount).filter(
        ChartOfAccount.is_active.is_(True),
        ChartOfAccount.is_posting.is_(True),
    ).all()

    for location in locations:
        if str(location["business_unit_name"] or "").lower() != "project catering":
            continue
        tokens = {
            token.lower()
            for token in str(location["name"] or "").replace("-", " ").split()
            if len(token) >= 3
        } | {
            token.lower()
            for token in str(location["code"] or "").replace("-", " ").split()
            if len(token) >= 3
        }
        inventory = [
            account for account in accounts
            if account.account_type == "ASSET"
            and account.normal_balance == "DEBIT"
            and str(account.account_subtype or "").upper() not in FUNDING_SUBTYPES
            and any(token in str(account.account_name or "").lower() for token in tokens)
        ]
        alias_tokens = set(tokens)
        for account in inventory:
            words = {
                word.lower().strip(".,()/")
                for word in str(account.account_name or "").replace("-", " ").split()
                if len(word.strip(".,()/")) >= 3
            }
            alias_tokens.update(
                word for word in words
                if word not in {"inv", "makanan", "minuman", "material", "cash", "sales", "clearance"}
            )
        ap = [
            account for account in accounts
            if account.account_type == "LIABILITY"
            and account.normal_balance == "CREDIT"
            and (
                "hutang usaha" in str(account.account_name or "").lower()
                or "payable" in str(account.account_name or "").lower()
            )
            and any(token in str(account.account_name or "").lower() for token in alias_tokens)
        ]
        print(f"{location['name']} ({location['code']}):")
        print("  AP candidates: " + (", ".join(account_label(x) for x in ap) if ap else "NONE"))
        print("  Inventory candidates: " + (", ".join(account_label(x) for x in inventory[:10]) if inventory else "NONE"))
        if not ap:
            all_ap = [
                account for account in accounts
                if account.account_type == "LIABILITY"
                and account.normal_balance == "CREDIT"
                and (
                    "hutang usaha" in str(account.account_name or "").lower()
                    or "payable" in str(account.account_name or "").lower()
                )
            ]
            print("  Nearby AP review list: " + ", ".join(account_label(x) for x in all_ap[:40]))


def apply_safe(db) -> None:
    vat = db.query(ChartOfAccount).filter(ChartOfAccount.account_number == VAT_CODE).first()
    if not vat or not vat.is_active or not vat.is_posting or vat.account_type != "ASSET" or vat.normal_balance != "DEBIT":
        raise RuntimeError(f"Cannot apply: VAT COA {VAT_CODE} is missing or not an active ASSET/DEBIT posting account")

    invoice_rules = []
    for event in INVOICE_EVENTS:
        invoice_rules.extend(active_rules(db, event))
    if not invoice_rules:
        raise RuntimeError("Cannot apply: no active Supplier Invoice posting rules exist")

    ap_ids = {rule.credit_account_id for rule in invoice_rules}
    if len(ap_ids) != 1:
        labels = ", ".join(account_label(db.get(ChartOfAccount, account_id)) for account_id in sorted(ap_ids))
        raise RuntimeError(f"Cannot apply: Supplier Invoice rules use different AP control accounts: {labels}")
    ap_id = next(iter(ap_ids))
    ap = db.get(ChartOfAccount, ap_id)
    if not ap or ap.account_type != "LIABILITY" or ap.normal_balance != "CREDIT" or not ap.is_active or not ap.is_posting:
        raise RuntimeError("Cannot apply: common Supplier Invoice credit account is not a valid AP liability")

    changed = 0
    for rule in invoice_rules:
        if rule.input_vat_account_id != vat.id:
            rule.input_vat_account_id = vat.id
            changed += 1

    payment_rules = active_rules(db, PAYMENT_EVENT)
    if not payment_rules:
        raise RuntimeError(
            "Cannot apply: no active SUPPLIER_PAYMENT rule exists. "
            "Create one in Finance Setup; debit must use the AP control account and credit must be any valid BANK/CASH control account. "
            "Actual payment credit is selected dynamically from the funding Bank Account."
        )

    for rule in payment_rules:
        if rule.debit_account_id != ap.id:
            rule.debit_account_id = ap.id
            changed += 1

    # Validate every touched rule before commit.
    svc = AccountingPostingRuleService(db)
    for rule in [*invoice_rules, *payment_rules]:
        svc.validate(
            rule.debit_account_id,
            rule.credit_account_id,
            rule.event_type,
            exclude_id=rule.id,
            active=True,
            input_vat_account_id=rule.input_vat_account_id,
            business_unit_id=rule.business_unit_id,
            location_id=rule.location_id,
        )

    db.commit()
    print(f"\nApplied {changed} deterministic posting-rule repair(s).")
    print(f"AP control account: {account_label(ap)}")
    print(f"Input VAT account: {account_label(vat)}")
    print("Supplier Payment bank/cash credit remains dynamic from the selected funding account.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply-safe", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        bank_issues = audit_bank_accounts(db)
        rule_issues = audit_rules(db)
        audit_location_candidates(db)
        if args.apply_safe:
            apply_safe(db)
            print("\n=== AFTER REPAIR ===")
            audit_rules(db)
        else:
            db.rollback()
            print("\nDry audit only; no data changed.")
        print(f"\nAudit summary: bank_account_issues={bank_issues}, posting_rule_issues={rule_issues}")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
