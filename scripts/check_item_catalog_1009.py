"""Read-only schema/catalog validation after the 10-09 Item Master migration."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import inspect, func
from app.core.database import SessionLocal
from app.models.product import Product


def main():
    with SessionLocal() as db:
        inspector = inspect(db.get_bind())
        required = {"products": {"catalog_type", "reference_cost_method"}, "goods_receipt_items": {"expense_account_id"}}
        for table, fields in required.items():
            missing = fields - {column["name"] for column in inspector.get_columns(table)}
            if missing:
                raise SystemExit(f"Migration required: {table} missing {', '.join(sorted(missing))}")
        counts = db.query(Product.catalog_type, Product.item_type, func.count(Product.id)).group_by(Product.catalog_type, Product.item_type).all()
        invalid = db.query(Product.id).filter(Product.catalog_type.notin_(["CATERING", "HOTEL"])).count()
        print(json.dumps({"schema": "OK", "catalogs": [{"catalog": catalog, "item_type": kind, "items": count} for catalog, kind, count in counts], "invalid_catalogs": invalid}, indent=2))
        print("READ ONLY: no items, prices, receipts, stock, journals or balances changed.")
        if invalid:
            raise SystemExit("Unexpected catalog values require inspection")


if __name__ == "__main__":
    main()
