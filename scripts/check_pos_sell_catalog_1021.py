"""Read-only EC2 schema/catalog validation."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import json
from sqlalchemy import inspect, text
from app.core.database import SessionLocal

def main():
    with SessionLocal() as db:
        db.execute(text('SET TRANSACTION READ ONLY'))
        columns = inspect(db.connection()).get_columns('sales_transactions')
        result = {'warehouse_optional': next(c['nullable'] for c in columns if c['name']=='warehouse_id'),
            'sell_catalogs': [dict(r) for r in db.execute(text("SELECT catalog_type, count(*) AS items FROM products WHERE item_type='SELL' AND is_active GROUP BY catalog_type")).mappings()]}
        print(json.dumps(result, default=str, indent=2))
        db.rollback()
    print('READ ONLY: no masters, sales, stock, journals, GL or openings changed.')
if __name__ == '__main__': main()
