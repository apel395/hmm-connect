#!/usr/bin/env python3
"""Create the DAIRY item subgroup under FOOD, safely and idempotently.

Dry-run by default. Use --apply to commit.
The code is chosen from the next available numeric suffix under the FOOD group
(e.g. FOOD code '1' with existing '1-1'..'1-8' becomes '1-9').
"""

from __future__ import annotations

import argparse
import re

from sqlalchemy import func

from app.core.database import SessionLocal
from app.models.item_group import ItemGroup
from app.models.item_subgroup import ItemSubgroup


def find_food_group(db) -> ItemGroup:
    row = (
        db.query(ItemGroup)
        .filter(func.upper(ItemGroup.name) == "FOOD")
        .first()
    )
    if not row:
        raise RuntimeError("Required Item Group 'FOOD' does not exist")
    return row


def find_existing_dairy(db) -> ItemSubgroup | None:
    return (
        db.query(ItemSubgroup)
        .filter(func.upper(ItemSubgroup.name) == "DAIRY")
        .first()
    )


def next_subgroup_code(db, group: ItemGroup) -> str:
    prefix = f"{group.code}-"
    used: set[int] = set()
    for (code,) in db.query(ItemSubgroup.code).filter(ItemSubgroup.group_id == group.id).all():
        match = re.fullmatch(re.escape(prefix) + r"(\d+)", code or "")
        if match:
            used.add(int(match.group(1)))
    suffix = 1
    while suffix in used:
        suffix += 1
    candidate = f"{prefix}{suffix}"
    if len(candidate) > 10:
        raise RuntimeError(f"Generated subgroup code '{candidate}' exceeds the 10-character limit")
    if db.query(ItemSubgroup).filter(ItemSubgroup.code == candidate).first():
        raise RuntimeError(f"Generated subgroup code '{candidate}' is already in use")
    return candidate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        food = find_food_group(db)
        existing = find_existing_dairy(db)
        if existing:
            print("DAIRY Item Subgroup seed summary:")
            print(f"  food_group={food.code} | {food.name}")
            print(f"  dairy_existing=1")
            print(f"  dairy_code={existing.code}")
            print(f"  dairy_group_id={existing.group_id}")
            print("No changes required.")
            db.rollback()
            return 0

        code = next_subgroup_code(db, food)
        print("DAIRY Item Subgroup seed summary:")
        print(f"  food_group={food.code} | {food.name}")
        print("  dairy_existing=0")
        print(f"  dairy_create=1")
        print(f"  proposed_code={code}")
        print(f"  proposed_name=DAIRY")

        if args.apply:
            db.add(ItemSubgroup(code=code, name="DAIRY", group_id=food.id, is_active=True))
            db.commit()
            print("DAIRY subgroup committed successfully.")
        else:
            db.rollback()
            print("Dry-run only; transaction rolled back. Use --apply to commit.")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
