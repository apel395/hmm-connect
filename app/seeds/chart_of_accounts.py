from __future__ import annotations

import base64
import gzip
import json

from sqlalchemy.orm import Session

from app.models.accounting_posting_rule import AccountingPostingRule
from app.models.bank_account import BankAccount
from app.models.business_unit import BusinessUnit
from app.models.chart_of_account import ChartOfAccount


# Exact normalized payload from Pak Ardi's approved COA.xlsx.
# Source rows: 302 unique COA codes. Existing production COA rows are never overwritten.
_COA_PAYLOAD_GZIP_B64 = """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"""

DEFAULT_CHART_OF_ACCOUNTS = [
    tuple(row)
    for row in json.loads(gzip.decompress(base64.b64decode(_COA_PAYLOAD_GZIP_B64)).decode("utf-8"))
]

PETTY_CASH_BUSINESS_UNITS = {
    "100-100-100": "Project Catering",
    "100-100-101": "Project Catering",
    "100-100-102": "Project Catering",
    "100-100-103": "Hotel",
    "100-100-104": "Hotel",
    "100-100-105": "Hotel",
    "100-100-106": "Project Catering",
    "100-100-107": "Project Catering",
    "100-100-108": "Project Catering",
    "100-100-109": "Project Catering",
    "100-100-110": "Project Catering",
    "100-100-111": "Hotel",
    "100-100-112": "Hotel",
    "100-100-990": "Hotel",
}

INPUT_VAT_ACCOUNT_NUMBER = "100-500-100"
INPUT_VAT_EVENTS = ("SUPPLIER_INVOICE_INVENTORY", "SUPPLIER_INVOICE_DIRECT_USE")


def _parent_number(code: str, available: set[str]) -> str | None:
    parts = code.split("-")
    for size in range(len(parts) - 1, 0, -1):
        candidate = "-".join(parts[:size])
        if candidate in available:
            return candidate
    return None


def seed_chart_of_accounts(db: Session) -> dict[str, int]:
    existing = {row.account_number: row for row in db.query(ChartOfAccount).all()}
    source_codes = {row[0] for row in DEFAULT_CHART_OF_ACCOUNTS}
    available_codes = set(existing) | source_codes
    created: dict[str, ChartOfAccount] = {}
    skipped = 0

    for code, name, account_type, normal_balance, row_kind, subtype, cash_flow, fs_group in sorted(
        DEFAULT_CHART_OF_ACCOUNTS,
        key=lambda row: (row[0].count("-"), row[0]),
    ):
        if code in existing:
            skipped += 1
            continue

        account = ChartOfAccount(
            account_number=code,
            account_name=name,
            account_type=account_type or "ASSET",
            normal_balance=normal_balance,
            cash_flow_category=cash_flow,
            account_subtype=subtype or "OTHER",
            financial_statement_group=fs_group,
            is_posting=(row_kind == "ACCOUNT"),
            is_system=False,
            is_active=True,
        )
        db.add(account)
        db.flush()
        existing[code] = account
        created[code] = account

    for code, account in created.items():
        parent = _parent_number(code, available_codes)
        if parent and parent in existing:
            account.parent_account_id = existing[parent].id

    return {"source": len(DEFAULT_CHART_OF_ACCOUNTS), "created": len(created), "existing_untouched": skipped}


def _business_unit(db: Session, name: str) -> BusinessUnit | None:
    return db.query(BusinessUnit).filter(BusinessUnit.name.ilike(name)).first()


def seed_cash_accounts(db: Session) -> dict[str, object]:
    created = 0
    existing_count = 0
    unresolved: list[str] = []

    for code, business_unit_name in PETTY_CASH_BUSINESS_UNITS.items():
        coa = db.query(ChartOfAccount).filter(ChartOfAccount.account_number == code).first()
        if not coa:
            unresolved.append(f"{code}: COA missing")
            continue
        if db.query(BankAccount).filter(BankAccount.coa_account_id == coa.id).first():
            existing_count += 1
            continue

        business_unit = _business_unit(db, business_unit_name)
        if not business_unit:
            unresolved.append(f"{code}: Business Unit '{business_unit_name}' not found")
            continue

        db.add(BankAccount(
            bank_name="Cash",
            account_name=coa.account_name,
            account_number=code,
            account_holder=None,
            currency="IDR",
            business_unit_id=business_unit.id,
            location_id=None,
            coa_account_id=coa.id,
            is_active=True,
        ))
        created += 1

    return {"created": created, "existing_untouched": existing_count, "unresolved": unresolved}


def seed_input_vat_posting(db: Session) -> dict[str, object]:
    account = (
        db.query(ChartOfAccount)
        .filter(ChartOfAccount.account_number == INPUT_VAT_ACCOUNT_NUMBER)
        .first()
    )
    if not account:
        return {"configured": 0, "missing": [f"COA {INPUT_VAT_ACCOUNT_NUMBER}"]}

    configured = 0
    missing: list[str] = []
    for event_type in INPUT_VAT_EVENTS:
        rule = (
            db.query(AccountingPostingRule)
            .filter(
                AccountingPostingRule.event_type == event_type,
                AccountingPostingRule.is_active.is_(True),
            )
            .first()
        )
        if not rule:
            missing.append(event_type)
            continue
        if rule.input_vat_account_id is None:
            rule.input_vat_account_id = account.id
            configured += 1

    return {"configured": configured, "missing": missing}
