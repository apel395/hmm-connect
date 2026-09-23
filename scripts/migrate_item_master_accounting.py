"""One-time Item Master accounting migration.

Adds treatment-aware accounting columns and normalizes the historical
GRESORIS typo to GROCERIES. Safe to run repeatedly.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from app.core.database import SessionLocal


def main():
    db = SessionLocal()
    try:
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
        print("Item Master migration committed")
        print(f"Products renamed GRESORIS -> GROCERIES: {product_result.rowcount}")
        print(f"Subgroups renamed GRESORIS -> GROCERIES: {subgroup_result.rowcount}")
    except Exception:
        db.rollback()
        print("ROLLED BACK")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
