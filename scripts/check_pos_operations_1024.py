"""Read-only migration/deployment check. Never creates shifts or changes balances."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import json
from sqlalchemy import inspect, text
from app.core.database import SessionLocal


def main():
    with SessionLocal() as db:
        inspector=inspect(db.connection())
        needed=('pos_outlet_policies','pos_tables','pos_cashier_sessions')
        schema={name:inspector.has_table(name) for name in needed}
        sale_columns={c['name'] for c in inspector.get_columns('sales_transactions')}
        schema['sales_columns']=all(c in sale_columns for c in ('pos_table_id','cashier_session_id','order_mode','event_name','order_request_key'))
        output={'schema':schema,'migration':db.execute(text('SELECT version_num FROM alembic_version')).scalars().all()}
        if all(schema.values()):
            output['policies']=[dict(r) for r in db.execute(text('SELECT location_id,department_id,order_mode FROM pos_outlet_policies ORDER BY location_id,department_id')).mappings()]
            output['shifts']=[dict(r) for r in db.execute(text('SELECT status,count(*) AS records FROM pos_cashier_sessions GROUP BY status')).mappings()]
            output['duplicate_open_tables']=db.execute(text("SELECT count(*) FROM (SELECT pos_table_id FROM sales_transactions WHERE status='DRAFT' AND pos_table_id IS NOT NULL GROUP BY pos_table_id HAVING count(*)>1) x")).scalar_one()
        print(json.dumps(output,indent=2,default=str))
        print('READ ONLY: no tables, shifts, orders, journals, stock or opening balances changed.')
        if not all(schema.values()):raise SystemExit(1)

if __name__=='__main__':main()
