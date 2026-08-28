"""Audit and safely normalize Item Master.

Default mode is read-only. --apply-safe only normalizes whitespace/case-safe fields
and refreshes market flags; it never deletes products or rewrites referenced IDs.
Duplicate groups and missing COA mappings are printed for manual merge decisions.
"""

from __future__ import annotations

import argparse
from collections import defaultdict

from sqlalchemy import func

from app.core.database import SessionLocal
from app.models.product import Product


MARKET_SUBGROUPS = {"VEGETABLES", "FRUIT"}


def normalized(value: str | None) -> str:
    return " ".join(str(value or "").strip().lower().split())


def audit(db) -> int:
    rows = db.query(Product).order_by(Product.id).all()
    by_code: dict[str, list[Product]] = defaultdict(list)
    by_name: dict[str, list[Product]] = defaultdict(list)
    issues = 0

    for row in rows:
        by_code[normalized(row.code)].append(row)
        by_name[normalized(row.name)].append(row)

    print("=== ITEM MASTER DUPLICATE CODES ===")
    for key, group in by_code.items():
        if key and len(group) > 1:
            issues += 1
            print(key, "=>", ", ".join(f"id={x.id}:{x.code}:{x.name}" for x in group))

    print("\n=== ITEM MASTER DUPLICATE NAMES ===")
    for key, group in by_name.items():
        if key and len(group) > 1:
            issues += 1
            print(key, "=>", ", ".join(f"id={x.id}:{x.code}:{x.name}" for x in group))

    print("\n=== ITEM MASTER MISSING CLASSIFICATION ===")
    for row in rows:
        if not row.group_code or not row.group_name or not row.subgroup_code or not row.subgroup_name:
            issues += 1
            print(f"id={row.id} {row.code} {row.name}: incomplete group/subgroup")

    print("\n=== ITEM MASTER MISSING DIRECT COA ===")
    for row in rows:
        missing = []
        if not row.inventory_account_id:
            missing.append("inventory")
        if not row.purchase_account_id:
            missing.append("consumption/expense")
        if not row.cogs_account_id:
            missing.append("cogs")
        if missing:
            issues += 1
            print(f"id={row.id} {row.code} {row.name}: {', '.join(missing)}")

    print(f"\nTotal audit issues: {issues}")
    return issues


def apply_safe(db) -> None:
    rows = db.query(Product).all()
    changed = 0
    for row in rows:
        next_code = row.code.strip().upper()
        next_name = " ".join(row.name.strip().split())
        next_group_code = row.group_code.strip().upper()
        next_group_name = " ".join(row.group_name.strip().split())
        next_subgroup_code = row.subgroup_code.strip().upper()
        next_subgroup_name = " ".join(row.subgroup_name.strip().split())
        next_market = next_subgroup_name.upper() in MARKET_SUBGROUPS
        values = (
            next_code,
            next_name,
            next_group_code,
            next_group_name,
            next_subgroup_code,
            next_subgroup_name,
            next_market,
        )
        current = (
            row.code,
            row.name,
            row.group_code,
            row.group_name,
            row.subgroup_code,
            row.subgroup_name,
            row.is_market_item,
        )
        if values != current:
            (
                row.code,
                row.name,
                row.group_code,
                row.group_name,
                row.subgroup_code,
                row.subgroup_name,
                row.is_market_item,
            ) = values
            changed += 1
    db.commit()
    print(f"Safely normalized {changed} Item Master rows. No rows were deleted or remapped.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply-safe", action="store_true")
    args = parser.parse_args()
    db = SessionLocal()
    try:
        audit(db)
        if args.apply_safe:
            apply_safe(db)
            print("\n=== AFTER SAFE NORMALIZATION ===")
            return 1 if audit(db) else 0
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
