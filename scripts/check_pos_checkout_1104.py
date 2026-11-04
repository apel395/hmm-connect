"""Read-only schema check for outlet checkout settings."""
import sys
import json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy import inspect,text
from app.core.database import SessionLocal
with SessionLocal() as db:
    if db.bind.dialect.name=='postgresql':db.execute(text('SET TRANSACTION READ ONLY'))
    schema=inspect(db.connection())
    checks={table:column in {c['name'] for c in schema.get_columns(table)} for table,column in [('pos_outlet_policies','checkout_settings'),('sales_transactions','checkout_snapshot')]}
    print(json.dumps({'mode':'READ_ONLY','schema':checks,'migration':db.execute(text('SELECT version_num FROM alembic_version')).scalars().all()},indent=2))
    if not all(checks.values()):raise SystemExit('Apply 20261104_pos_checkout before release')
print('READ ONLY CHECK: no settings, sales, stock, journals or opening balances changed.')
