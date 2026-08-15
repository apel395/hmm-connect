#!/usr/bin/env python3
"""Replace historical PIM-* product codes with the HMM item-code pattern.

Scope is intentionally narrow: only products whose current code starts with
``PIM-`` are changed. Product IDs and all foreign-key relationships remain
untouched.

The historical Purchasing seed reserved group 9 / subgroup 9-1 for imported PO
items. HMM item codes encode that subgroup in the same structure as the original
master data, so imported products become:

    9-100001
    9-100002
    ...

Allocation starts after the highest existing 9-1xxxxx sequence and checks every
candidate against all product codes, making the operation collision-safe and
idempotent.

Dry-run is the default. Use ``--apply`` to commit.
"""

from __future__ import annotations

import argparse
import re
import sys

from app.core.database import SessionLocal
from app.models.item_group import ItemGroup
from app.models.item_subgroup import ItemSubgroup
from app.models.product import Product

GROUP_CODE = "9"
GROUP_NAME = "PURCHASING"
SUBGROUP_CODE = "9-1"
SUBGROUP_NAME = "IMPORTED PO ITEM"
CODE_RE = re.compile(r"^9-1(\d{5})$")


def ensure_imported_classification(db) -> None:
    group = db.query(ItemGroup).filter(ItemGroup.code == GROUP_CODE).first()
    if group is None:
        group = ItemGroup(code=GROUP_CODE, name=GROUP_NAME, is_active=True)
        db.add(group)
        db.flush()
    else:
        group.name = GROUP_NAME
        group.is_active = True

    subgroup = db.query(ItemSubgroup).filter(ItemSubgroup.code == SUBGROUP_CODE).first()
    if subgroup is None:
        subgroup = ItemSubgroup(
            code=SUBGROUP_CODE,
            name=SUBGROUP_NAME,
            group_id=group.id,
            is_active=True,
        )
        db.add(subgroup)
    else:
        subgroup.name = SUBGROUP_NAME
        subgroup.group_id = group.id
        subgroup.is_active = True
    db.flush()


def next_sequence(occupied: set[str]) -> int:
    maximum = 0
    for code in occupied:
        match = CODE_RE.fullmatch(code.upper())
        if match:
            maximum = max(maximum, int(match.group(1)))
    return maximum + 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize PIM-* product codes to HMM 9-1xxxxx codes")
    parser.add_argument("--apply", action="store_true", help="Commit changes; default is preview only")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        ensure_imported_classification(db)
        products = db.query(Product).order_by(Product.name, Product.id).all()
        occupied = {str(product.code or "").upper() for product in products if product.code}
        targets = [product for product in products if str(product.code or "").upper().startswith("PIM-")]

        sequence = next_sequence(occupied)
        changes: list[tuple[str, str, str]] = []

        for product in targets:
            while sequence < 100000:
                candidate = f"9-1{sequence:05d}"
                sequence += 1
                if candidate.upper() not in occupied:
                    break
            else:
                raise RuntimeError("Imported Purchasing item code range 9-100001..9-199999 is exhausted")

            old_code = str(product.code)
            occupied.add(candidate.upper())
            product.code = candidate

            # PIM products were created by the historical Purchasing seed under
            # this reserved classification. Normalize the stored codes too when
            # they still carry those placeholder values.
            if str(product.group_name or "").upper() == GROUP_NAME or str(product.group_code or "").upper() in {"PURCHASING", GROUP_CODE}:
                product.group_code = GROUP_CODE
                product.group_name = GROUP_NAME
                product.subgroup_code = SUBGROUP_CODE
                product.subgroup_name = SUBGROUP_NAME

            changes.append((old_code, candidate, product.name))

        print("PIM item-code normalization preview:")
        print(f"  candidates={len(targets)}")
        print(f"  changes={len(changes)}")
        for old_code, new_code, name in changes[:20]:
            print(f"  {old_code} -> {new_code} | {name}")
        if len(changes) > 20:
            print(f"  ... {len(changes) - 20} more")

        duplicate_count = len(occupied) - len(set(occupied))
        if duplicate_count:
            raise RuntimeError("Duplicate product code detected during normalization")

        if args.apply:
            db.commit()
            print("Item-code normalization committed successfully.")
        else:
            db.rollback()
            print("Dry-run complete; transaction rolled back. Re-run with --apply to commit.")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
