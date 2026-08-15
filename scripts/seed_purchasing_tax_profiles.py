"""Seed high-confidence purchasing tax profiles into Product master.

Generated from historical HMM purchasing workbooks and reviewed against:
- PP 49 Tahun 2022
- PMK 131 Tahun 2024

Safety:
- Default mode is DRY RUN.
- Only HIGH-confidence exact product-name matches are changed.
- Existing products not in this mapping are untouched.
- MEDIUM/LOW-confidence items remain REVIEW_REQUIRED.
- Re-running is idempotent.

Usage:
    python scripts/seed_purchasing_tax_profiles.py
    python scripts/seed_purchasing_tax_profiles.py --apply
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import zlib
from decimal import Decimal

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.product import Product

STANDARD_RATE = Decimal("11.0000")
ZERO = Decimal("0.0000")
EXEMPT_REFERENCE = "PP 49 Tahun 2022"
STANDARD_REFERENCE = "PMK 131 Tahun 2024"

# Compressed JSON mapping: {exact historical purchasing item name: EXEMPT|STANDARD}.
# Contains 943 HIGH-confidence items: 376 EXEMPT and 567 STANDARD.
MAPPING_B64 = "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"


def normalize_name(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip()).casefold()


def load_mapping() -> dict[str, str]:
    raw = zlib.decompress(base64.b64decode(MAPPING_B64)).decode("utf-8")
    mapping = json.loads(raw)
    return {normalize_name(name): category for name, category in mapping.items()}


def desired_profile(category: str) -> dict[str, object]:
    if category == "EXEMPT":
        return {
            "tax_category": "EXEMPT",
            "is_taxable": False,
            "tax_rate": ZERO,
            "tax_reason": "High-confidence qualifying exempt purchasing item classification.",
            "tax_reference": EXEMPT_REFERENCE,
        }
    return {
        "tax_category": "STANDARD",
        "is_taxable": True,
        "tax_rate": STANDARD_RATE,
        "tax_reason": "High-confidence standard taxable purchasing item classification.",
        "tax_reference": STANDARD_REFERENCE,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed HMM purchasing tax profiles.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Commit matching tax-profile changes. Without this flag the script is dry-run only.",
    )
    args = parser.parse_args()

    mapping = load_mapping()
    db = SessionLocal()
    changed = 0
    matched = 0
    already_correct = 0
    unmatched_mapping = set(mapping)

    try:
        products = db.execute(select(Product).order_by(Product.id)).scalars().all()

        for product in products:
            key = normalize_name(product.name)
            category = mapping.get(key)
            if category is None:
                continue

            matched += 1
            unmatched_mapping.discard(key)
            profile = desired_profile(category)

            current = (
                product.tax_category,
                bool(product.is_taxable),
                Decimal(product.tax_rate or 0),
                product.tax_reason,
                product.tax_reference,
            )
            desired = (
                profile["tax_category"],
                profile["is_taxable"],
                profile["tax_rate"],
                profile["tax_reason"],
                profile["tax_reference"],
            )

            if current == desired:
                already_correct += 1
                continue

            changed += 1
            print(
                f"{'[APPLY]' if args.apply else '[DRY-RUN]'} "
                f"{product.code} | {product.name} | "
                f"{product.tax_category}/{product.tax_rate} -> "
                f"{profile['tax_category']}/{profile['tax_rate']}"
            )

            product.tax_category = profile["tax_category"]
            product.is_taxable = profile["is_taxable"]
            product.tax_rate = profile["tax_rate"]
            product.tax_reason = profile["tax_reason"]
            product.tax_reference = profile["tax_reference"]

        if args.apply:
            db.commit()
        else:
            db.rollback()

        print()
        print("Purchasing tax profile seed summary")
        print(f"  Mode              : {'APPLY' if args.apply else 'DRY RUN'}")
        print(f"  Mapping entries   : {len(mapping)}")
        print(f"  Products matched  : {matched}")
        print(f"  Changed           : {changed}")
        print(f"  Already correct   : {already_correct}")
        print(f"  Mapping not in DB : {len(unmatched_mapping)}")
        print(f"  Left untouched    : {len(products) - matched}")
        print()
        if unmatched_mapping:
            sample = sorted(unmatched_mapping)[:20]
            print("Sample mapping names not found in Product master:")
            for name in sample:
                print(f"  - {name}")
            if len(unmatched_mapping) > len(sample):
                print(f"  ... and {len(unmatched_mapping) - len(sample)} more")
        print()
        print("NOTE: MEDIUM/LOW-confidence purchasing items are intentionally not seeded and remain REVIEW_REQUIRED.")
        if not args.apply:
            print("No database changes were committed. Re-run with --apply after reviewing this output.")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
