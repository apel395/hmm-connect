"""Prepare Item Master accounting treatment.

Preview by default. Use --apply to write.

Rules are intentionally conservative:
- GRESORIS is normalized to GROCERIES.
- Existing 100-300-* inventory mappings are reported as STOCK candidates only.
- Direct-use/non-stock/fixed-asset treatment is NOT guessed from product name/group.
- No existing product is auto-classified; every treatment must be explicitly confirmed.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from app.core.database import SessionLocal


def ensure_schema(db):
    db.execute(text("""
        ALTER TABLE products
        ADD COLUMN IF NOT EXISTS inventory_treatment VARCHAR(20)
        NOT NULL DEFAULT 'REVIEW_REQUIRED'
    """))
    db.execute(text("""
        ALTER TABLE products
        ADD COLUMN IF NOT EXISTS asset_account_id INTEGER NULL
    """))
    db.execute(text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'fk_products_asset_account_id'
            ) THEN
                ALTER TABLE products
                ADD CONSTRAINT fk_products_asset_account_id
                FOREIGN KEY (asset_account_id)
                REFERENCES chart_of_accounts(id);
            END IF;
        END $$;
    """))
    db.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_products_inventory_treatment
        ON products (inventory_treatment)
    """))


def preview(db):
    typo_products = db.execute(text("""
        SELECT COUNT(*)
        FROM products
        WHERE UPPER(TRIM(subgroup_name)) = 'GRESORIS'
    """)).scalar_one()

    typo_subgroups = db.execute(text("""
        SELECT COUNT(*)
        FROM item_subgroups
        WHERE UPPER(TRIM(name)) = 'GRESORIS'
    """)).scalar_one()

    stock_candidates = db.execute(text("""
        SELECT
            p.id,
            p.code,
            p.name,
            p.group_name,
            p.subgroup_name,
            coa.account_number,
            coa.account_name
        FROM products p
        JOIN chart_of_accounts coa ON coa.id = p.inventory_account_id
        WHERE COALESCE(p.inventory_treatment, 'REVIEW_REQUIRED') = 'REVIEW_REQUIRED'
          AND coa.is_active = TRUE
          AND coa.is_posting = TRUE
          AND coa.account_type = 'ASSET'
          AND coa.normal_balance = 'DEBIT'
          AND coa.account_number LIKE '100-300-%'
        ORDER BY p.code
    """)).mappings().all()

    unresolved = db.execute(text("""
        SELECT
            p.id,
            p.code,
            p.name,
            p.group_name,
            p.subgroup_name,
            p.tax_category,
            p.inventory_account_id,
            p.purchase_account_id,
            p.cogs_account_id
        FROM products p
        WHERE COALESCE(p.inventory_treatment, 'REVIEW_REQUIRED') = 'REVIEW_REQUIRED'
        ORDER BY p.group_name, p.subgroup_name, p.code
    """)).mappings().all()

    print("=== ITEM MASTER MIGRATION PREVIEW ===")
    print(f"GRESORIS product rows : {typo_products}")
    print(f"GRESORIS subgroup rows: {typo_subgroups}")
    print(f"Possible STOCK candidates: {len(stock_candidates)}")
    print(f"Still needs review     : {len(unresolved)}")

    if stock_candidates:
        print("\n=== POSSIBLE STOCK CANDIDATES (REVIEW ONLY) ===")
        for row in stock_candidates:
            print(
                f"{row['code']:<16} | {row['name']:<40} | "
                f"{row['account_number']} — {row['account_name']}"
            )

    print("\n=== MANUAL REVIEW SAMPLE ===")
    for row in unresolved[:100]:
        print(
            f"{row['code']:<16} | {row['name']:<36} | "
            f"{row['group_name'] or ''}/{row['subgroup_name'] or ''} | "
            f"tax={row['tax_category']} | "
            f"inv={row['inventory_account_id']} exp={row['purchase_account_id']} cogs={row['cogs_account_id']}"
        )
    if len(unresolved) > 100:
        print(f"... {len(unresolved) - 100} more")

    return stock_candidates


def apply(db):
    ensure_schema(db)

    product_result = db.execute(text("""
        UPDATE products
        SET subgroup_name = 'GROCERIES'
        WHERE UPPER(TRIM(subgroup_name)) = 'GRESORIS'
    """))
    subgroup_result = db.execute(text("""
        UPDATE item_subgroups
        SET name = 'GROCERIES'
        WHERE UPPER(TRIM(name)) = 'GRESORIS'
    """))

    db.commit()
    print("\n=== APPLIED ===")
    print(f"Products renamed GRESORIS -> GROCERIES: {product_result.rowcount}")
    print(f"Subgroups renamed GRESORIS -> GROCERIES: {subgroup_result.rowcount}")
    print("Existing products were NOT auto-classified.")
    print("All treatments remain REVIEW_REQUIRED until explicitly confirmed in Item Master.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        # Existing deployments do not have the new columns yet, so preview must
        # inspect schema first without mutating it.
        has_treatment = db.execute(text("""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'products'
                  AND column_name = 'inventory_treatment'
            )
        """)).scalar_one()

        if not has_treatment:
            print("inventory_treatment column is not installed yet.")
            print("Run with --apply to install schema and perform the safe migration.")
            if not args.apply:
                typo_products = db.execute(text("""
                    SELECT COUNT(*) FROM products
                    WHERE UPPER(TRIM(subgroup_name)) = 'GRESORIS'
                """)).scalar_one()
                typo_subgroups = db.execute(text("""
                    SELECT COUNT(*) FROM item_subgroups
                    WHERE UPPER(TRIM(name)) = 'GRESORIS'
                """)).scalar_one()
                stock_candidates = db.execute(text("""
                    SELECT COUNT(*)
                    FROM products p
                    JOIN chart_of_accounts coa ON coa.id = p.inventory_account_id
                    WHERE coa.is_active = TRUE
                      AND coa.is_posting = TRUE
                      AND coa.account_type = 'ASSET'
                      AND coa.normal_balance = 'DEBIT'
                      AND coa.account_number LIKE '100-300-%'
                """)).scalar_one()
                print(f"GRESORIS product rows : {typo_products}")
                print(f"GRESORIS subgroup rows: {typo_subgroups}")
                print(f"Safe STOCK candidates : {stock_candidates}")
                return

        if args.apply:
            apply(db)

        preview(db)

    except Exception:
        db.rollback()
        print("ROLLED BACK")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
