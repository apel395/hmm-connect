#!/usr/bin/env python3
"""Replace historical PIM-* codes with the HMM Item Master XLS format.

Book1.xlsx defines item codes as:
    <group>-<subgroup><5 digit sequence>

Examples:
    1-1 MEAT       -> 1-100001
    1-2 POULTRY    -> 1-200001
    3-4 STATIONARY -> 3-400001

Only PIM-* products are targeted. Product IDs and foreign-key relationships are
left untouched. Existing valid HMM subgroup data is preferred; legacy placeholder
products are classified from their item names. Any unresolved product is reported
and --apply is refused, preventing a fake/default category from being written.

Dry-run is the default. Use --apply to commit.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter

from app.core.database import SessionLocal
from app.models.item_group import ItemGroup
from app.models.item_subgroup import ItemSubgroup
from app.models.product import Product
from scripts.hmm_item_code_format import ITEM_CLASSES, allocate_code, class_from_product, infer_class


def ensure_taxonomy(db) -> None:
    groups: dict[str, ItemGroup] = {}
    for item_class in ITEM_CLASSES.values():
        group = groups.get(item_class.group_code)
        if group is None:
            group = db.query(ItemGroup).filter(ItemGroup.code == item_class.group_code).first()
            if group is None:
                group = ItemGroup(code=item_class.group_code, name=item_class.group_name, is_active=True)
                db.add(group)
                db.flush()
            else:
                group.name = item_class.group_name
                group.is_active = True
            groups[item_class.group_code] = group

        subgroup = db.query(ItemSubgroup).filter(ItemSubgroup.code == item_class.subgroup_code).first()
        if subgroup is None:
            db.add(ItemSubgroup(
                code=item_class.subgroup_code,
                name=item_class.subgroup_name,
                group_id=group.id,
                is_active=True,
            ))
        else:
            subgroup.name = item_class.subgroup_name
            subgroup.group_id = group.id
            subgroup.is_active = True
    db.flush()


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize PIM-* product codes using Book1.xlsx Item Master format")
    parser.add_argument("--apply", action="store_true", help="Commit changes; default is preview only")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        ensure_taxonomy(db)
        products = db.query(Product).order_by(Product.name, Product.id).all()
        occupied = {str(product.code or "").upper() for product in products if product.code}
        targets = [product for product in products if str(product.code or "").upper().startswith("PIM-")]

        resolved = []
        unresolved = []
        counts = Counter()

        for product in targets:
            item_class = class_from_product(product) or infer_class(product.name)
            if item_class is None:
                unresolved.append(product)
                continue
            resolved.append((product, item_class))
            counts[f"{item_class.subgroup_code} {item_class.subgroup_name}"] += 1

        print("PIM Item Master normalization preview:")
        print(f"  candidates={len(targets)}")
        print(f"  resolved={len(resolved)}")
        print(f"  unresolved={len(unresolved)}")
        for key in sorted(counts):
            print(f"  {key}: {counts[key]}")

        if unresolved:
            print("\nUnresolved items (first 50):")
            for product in unresolved[:50]:
                print(f"  {product.code} | {product.name}")
            if len(unresolved) > 50:
                print(f"  ... {len(unresolved) - 50} more")
            if args.apply:
                raise RuntimeError(
                    "Refusing --apply: some PIM items cannot be mapped to the XLS group/subgroup taxonomy"
                )

        changes = []
        for product, item_class in resolved:
            old_code = str(product.code)
            new_code = allocate_code(item_class, occupied)
            product.code = new_code
            product.group_code = item_class.group_code
            product.group_name = item_class.group_name
            product.subgroup_code = item_class.subgroup_code
            product.subgroup_name = item_class.subgroup_name
            changes.append((old_code, new_code, product.name, item_class.subgroup_name))

        print("\nCode changes (first 30):")
        for old_code, new_code, name, subgroup in changes[:30]:
            print(f"  {old_code} -> {new_code} | {subgroup} | {name}")
        if len(changes) > 30:
            print(f"  ... {len(changes) - 30} more")

        if args.apply:
            db.commit()
            print("Item Master code normalization committed successfully.")
        else:
            db.rollback()
            print("Dry-run complete; transaction rolled back.")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
