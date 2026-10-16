"""Read-only schema/evidence check; does not reinterpret legacy receiving."""
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    from sqlalchemy import text
    from app.core.database import engine
    with engine.connect() as db:
        transaction = db.begin()
        try:
            db.exec_driver_sql("SET TRANSACTION READ ONLY")
            columns = set(db.execute(text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = current_schema() AND table_name = 'goods_receipt_items'
            """)).scalars())
            required = {"destination_type", "destination_override_reason"}
            result = {"schema": "OK" if required <= columns else "MIGRATION_REQUIRED", "columns": {name: name in columns for name in sorted(required)}}
            result["migration"] = list(db.execute(text("SELECT version_num FROM alembic_version")).scalars())
            if required <= columns:
                result["receipt_destinations"] = [dict(row) for row in db.execute(text("SELECT destination_type, count(*) AS receipts FROM goods_receipts GROUP BY destination_type ORDER BY destination_type")).mappings()]
                result["legacy_lines_preserving_header"] = db.execute(text("SELECT count(*) FROM goods_receipt_items WHERE destination_type IS NULL")).scalar_one()
            print(json.dumps(result, indent=2))
            print("READ ONLY: no receiving, stock, journal, invoice or Item Master changed.")
        finally:
            transaction.rollback()


if __name__ == "__main__":
    main()
