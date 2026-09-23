"""Register active cash/bank COAs as funding accounts.

Idempotent. Existing bank_accounts rows are preserved and enabled for payments.
New rows are created as global accounts (location_id=NULL) for the selected BU.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal
from app.models.bank_account import BankAccount
from app.models.business_unit import BusinessUnit
from app.models.chart_of_account import ChartOfAccount

CASH_SUBTYPES = {"BANK", "CASH", "PETTY_CASH"}


def args():
    p = argparse.ArgumentParser()
    p.add_argument("--business-unit-code", required=True)
    p.add_argument("--apply", action="store_true")
    return p.parse_args()


def bank_name(account: ChartOfAccount) -> str:
    name = str(account.account_name or "").upper()
    if "MANDIRI" in name:
        return "Bank Mandiri"
    if "BCA" in name:
        return "Bank BCA"
    if "BNI" in name:
        return "Bank BNI"
    if "BRI" in name:
        return "Bank BRI"
    if account.account_subtype == "PETTY_CASH":
        return "Petty Cash"
    if account.account_subtype == "CASH":
        return "Cash"
    return "Bank"


def external_number(account: ChartOfAccount) -> str:
    # Prefer the real bank-account number embedded in the COA name.
    digit_groups = re.findall(r"\d+", str(account.account_name or ""))
    joined = "".join(digit_groups)
    if len(joined) >= 10:
        return joined
    return f"COA-{account.account_number}"


def main():
    a = args()
    db = SessionLocal()
    try:
        bu = db.query(BusinessUnit).filter(
            BusinessUnit.code == a.business_unit_code,
            BusinessUnit.is_active.is_(True),
        ).first()
        if not bu:
            raise RuntimeError(f"Active Business Unit {a.business_unit_code!r} not found")

        accounts = db.query(ChartOfAccount).filter(
            ChartOfAccount.is_active.is_(True),
            ChartOfAccount.is_posting.is_(True),
            ChartOfAccount.account_type == "ASSET",
            ChartOfAccount.account_subtype.in_(CASH_SUBTYPES),
        ).order_by(ChartOfAccount.account_number).all()

        print(f"Business Unit: {bu.code} - {bu.name}")
        print(f"Eligible cash/bank COAs: {len(accounts)}")

        created = updated = 0
        for coa in accounts:
            row = db.query(BankAccount).filter(BankAccount.coa_account_id == coa.id).first()
            if row:
                changed = False
                if not row.is_active:
                    row.is_active = True
                    changed = True
                if not row.is_payment_account:
                    row.is_payment_account = True
                    changed = True
                if changed:
                    updated += 1
                print(f"EXIST  {coa.account_number} | {coa.account_name} | {row.account_number}")
                continue

            row = BankAccount(
                bank_name=bank_name(coa),
                account_name=coa.account_name,
                account_number=external_number(coa),
                account_holder=bu.name,
                currency="IDR",
                business_unit_id=bu.id,
                location_id=None,
                coa_account_id=coa.id,
                is_active=True,
                is_payment_account=True,
            )
            db.add(row)
            created += 1
            print(f"NEW    {coa.account_number} | {coa.account_name} | {row.account_number}")

        if a.apply:
            db.commit()
            print(f"COMMITTED created={created} updated={updated}")
        else:
            db.rollback()
            print(f"DRY RUN created={created} updated={updated}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
