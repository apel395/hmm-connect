"""Read-only Item Master migration and department checks."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import json
from sqlalchemy import inspect, text
from app.core.database import SessionLocal

with SessionLocal() as db:
    exists=inspect(db.connection()).has_table('item_departments')
    print(json.dumps({'schema':'OK' if exists else 'MIGRATION_REQUIRED',
        'departments_assigned':db.execute(text('SELECT count(*) FROM item_departments')).scalar_one() if exists else None}))
    db.rollback()
print('READ ONLY: no master data, stock or accounting changed.')
