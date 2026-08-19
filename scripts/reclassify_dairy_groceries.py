#!/usr/bin/env python3
"""Safely reclassify existing Item Master rows for Sprint 2.

Business rules:
- Milk-derived products belong to DAIRY.
- Canned products belong to GROCERIES.

Dry-run by default. Use --apply to commit.
The script never creates new group/subgroup master rows. It requires existing
DAIRY and GROCERIES subgroups and fails cleanly if they are missing.
"""

from __future__ import annotations

import argparse
import re

from sqlalchemy import func

from app.core.database import SessionLocal
from app.models.item_subgroup import ItemSubgroup
from app.models.product import Product

DAIRY_PATTERNS = tuple(re.compile(pattern) for pattern in (
    r"\bsusu\b",
    r"\bmilk\b",
    r"\bkeju\b",
    r"\bcheese\b",
    r"\byogh?urt\b",
    r"\bcream\b",
    r"\bbutter\b",
))

# Explicit non-dairy products containing an otherwise valid dairy token.
# Margarine stays excluded until classification policy explicitly includes it.
DAIRY_EXCLUSIONS = tuple(re.compile(pattern) for pattern in (
    r"\bmilk tea(?: powder)?\b",
    r"\bcream cleaner\b",
    r"\bcheese ?cloth\b",
    r"\bbutter knife\b",
    r"\bbody (?:milk|butter)\b",
    r"\bmargarine\b",
))

CANNED_PATTERN = re.compile(r"\b(?:kaleng|canned)\b")


def normalized(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def find_subgroup(db, name: str) -> ItemSubgroup:
    row = (
        db.query(ItemSubgroup)
        .filter(func.upper(ItemSubgroup.name) == name.upper())
        .first()
    )
    if not row:
        raise RuntimeError(f"Required Item Subgroup '{name}' does not exist")
    return row


def is_dairy(product: Product) -> bool:
    name = normalized(product.name)
    return not any(pattern.search(name) for pattern in DAIRY_EXCLUSIONS) and any(
        pattern.search(name) for pattern in DAIRY_PATTERNS
    )


def is_canned(product: Product) -> bool:
    name = normalized(product.name)
    uom = normalized(product.uom)
    usage_uom = normalized(product.usage_uom)
    return bool(CANNED_PATTERN.search(name)) or uom in {"can", "cans"} or usage_uom in {"can", "cans"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        dairy = find_subgroup(db, "DAIRY")
        groceries = find_subgroup(db, "GROCERIES")

        products = db.query(Product).order_by(Product.code).all()
        dairy_candidates = []
        grocery_candidates = []
        overlap_candidates = []
        dairy_updates = []
        grocery_updates = []
        unchanged = 0

        for product in products:
            # Canned rule wins when a product happens to contain a dairy keyword,
            # because the business explicitly wants all canned products in GROCERIES.
            target = None
            reason = None
            dairy_match = is_dairy(product)
            canned_match = is_canned(product)
            if dairy_match:
                dairy_candidates.append({"code": product.code, "name": product.name})
            if canned_match:
                grocery_candidates.append({"code": product.code, "name": product.name})
            if dairy_match and canned_match:
                overlap_candidates.append({"code": product.code, "name": product.name})
            if canned_match:
                target = groceries
                reason = "canned"
            elif dairy_match:
                target = dairy
                reason = "milk-derived"

            if target is None or product.subgroup_code == target.code:
                unchanged += 1
                continue

            item = {
                "id": product.id,
                "code": product.code,
                "name": product.name,
                "from": product.subgroup_name,
                "to": target.name,
                "reason": reason,
            }
            if target.id == groceries.id:
                grocery_updates.append(item)
            else:
                dairy_updates.append(item)

            if args.apply:
                product.group_code = target.group.code
                product.group_name = target.group.name
                product.subgroup_code = target.code
                product.subgroup_name = target.name

        print("Sprint 2 Item Classification")
        print(f"  dairy_candidates={len(dairy_candidates)}")
        print(f"  groceries_candidates={len(grocery_candidates)}")
        print(f"  overlap_candidates={len(overlap_candidates)}")
        print(f"  unchanged_rows={unchanged}")
        print(f"  rows_to_update={len(dairy_updates) + len(grocery_updates)}")

        for label, rows in (("DAIRY", dairy_updates), ("GROCERIES", grocery_updates)):
            if rows:
                print(f"\n{label} preview:")
                for row in rows[:50]:
                    print(f"  {row['code']} | {row['name']} | {row['from']} -> {row['to']} | {row['reason']}")
                if len(rows) > 50:
                    print(f"  ... and {len(rows) - 50} more")

        if args.apply:
            db.commit()
            print("\nClassification changes committed successfully.")
        else:
            db.rollback()
            print("\nDry run only. Re-run with --apply after reviewing the preview.")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
