"""Read-only schema verification; no order or financial changes."""
import json
from sqlalchemy import inspect, text
from app.core.database import SessionLocal

with SessionLocal() as db:
    db.execute(text('SET TRANSACTION READ ONLY'))
    schema = inspect(db.connection())
    columns = {c['name']: c for c in schema.get_columns('sales_transactions')}
    checks = {c['name'] for c in schema.get_check_constraints('sales_transactions')}
    result = {'guest_count': 'guest_count' in columns,
              'nullable': columns.get('guest_count', {}).get('nullable', False),
              'positive_constraint': 'ck_sales_guest_count_positive' in checks}
    revisions = list(db.execute(text('SELECT version_num FROM alembic_version')).scalars())
    print(json.dumps({'mode':'READ_ONLY', 'schema':result, 'migration':revisions}, indent=2))
    db.rollback()
    if not all(result.values()):
        raise SystemExit('Apply 20261105_pos_guests before releasing the guest-count API')
print('READ ONLY CHECK: no settings, sales, stock, journals or opening balances changed.')
