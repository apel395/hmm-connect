"""Read-only check of the asset Item Master intake migration and COA."""
from pathlib import Path
import sys
import json
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sqlalchemy import inspect, text
from app.core.database import SessionLocal
with SessionLocal() as db:
    db.execute(text('SET TRANSACTION READ ONLY'))
    columns = {r['name']: r['nullable'] for r in inspect(db.connection()).get_columns('fixed_assets')}
    expected = ['acquisition_date','acquisition_cost','business_unit_id','created_by_id','net_book_value']
    if not all(columns.get(c) for c in expected): raise RuntimeError('Apply 20261013_asset_master_intake before deployment')
    print(json.dumps({'migration': db.execute(text('SELECT version_num FROM alembic_version')).scalars().all(),
      'pending_columns': {c: columns[c] for c in expected},
      'operating_equipment_accounts': [dict(r) for r in db.execute(text("SELECT id,account_number,account_name,is_active,is_posting,normal_balance FROM chart_of_accounts WHERE account_number LIKE '100-900-%' ORDER BY account_number")).mappings()],
      'register_statuses': [dict(r) for r in db.execute(text('SELECT status,count(*) AS records FROM fixed_assets GROUP BY status')).mappings()]}, indent=2, default=str))
    db.rollback()
print('READ ONLY: no items, assets, stock, journals, GL or openings changed.')
