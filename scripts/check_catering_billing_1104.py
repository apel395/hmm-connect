"""Read-only schema check after the Catering billing migration."""
import json
from sqlalchemy import inspect, text
from app.core.database import SessionLocal

with SessionLocal() as db:
    schema = inspect(db.connection())
    columns = {table: {column['name'] for column in schema.get_columns(table)}
               for table in ('sales_transactions', 'sales_transaction_lines')}
    checks = {
        'catering_location_billing': schema.has_table('catering_location_billing'),
        'invoice_snapshot': 'billing_details' in columns['sales_transactions'],
        'service_details': {'description', 'registration_number', 'service_period_from', 'service_period_to'} <= columns['sales_transaction_lines'],
    }
    revisions = db.execute(text('SELECT version_num FROM alembic_version')).scalars().all()
    print(json.dumps({'mode': 'READ_ONLY', 'schema': checks, 'migration': revisions}, indent=2))
    if not all(checks.values()):
        raise SystemExit('Apply 20261104_catering_billing before releasing the API')
print('READ ONLY CHECK: no settings, invoices, stock, journals or opening balances changed.')
