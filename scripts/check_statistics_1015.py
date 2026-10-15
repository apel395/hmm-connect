"""Read-only schema/COA check; no sample quantities or financial writes."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import json
from sqlalchemy import inspect, text
from app.core.database import SessionLocal


def main():
    with SessionLocal() as db:
        schema = inspect(db.get_bind())
        if not schema.has_table('statistical_values'):
            raise SystemExit('Missing statistical_values: run the statistics migration first')
        row = db.execute(text("SELECT account_number,account_name,account_type,is_posting FROM chart_of_accounts WHERE account_number='900'")).mappings().one()
        if row['account_type'] != 'STATISTIC' or row['is_posting']:
            raise SystemExit('COA 900 must be STATISTIC and non-financial-posting')
        print(json.dumps({'schema':'OK','migration':db.execute(text('SELECT version_num FROM alembic_version')).scalars().all(),'header':dict(row),'statistical_records':db.execute(text('SELECT count(*) FROM statistical_values')).scalar_one()},indent=2,default=str))
        print('READ ONLY: no accounts, actuals, budgets, journals, GL or balances changed.')


if __name__ == '__main__':
    main()
