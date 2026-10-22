"""Read-only POS revenue snapshot and direct account-choice check."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import json
from sqlalchemy import inspect, text
from app.core.database import SessionLocal
from app.models.business_unit import BusinessUnit
from app.services.pos_revenue import revenue_accounts


def main():
    with SessionLocal() as db:
        db.execute(text('SET TRANSACTION READ ONLY'))
        columns = {c['name'] for c in inspect(db.connection()).get_columns('sales_transactions')}
        result = {'revenue_snapshot_ready': 'revenue_account_id' in columns, 'revenue_choices': []}
        for unit in db.query(BusinessUnit).filter(BusinessUnit.is_active.is_(True)).all():
            result['revenue_choices'].append({'unit':unit.name, 'accounts':[{'id':a.id,'code':a.account_number,'name':a.account_name} for a in revenue_accounts(db,unit.id).all()]})
        print(json.dumps(result, indent=2))
        db.rollback()
    print('READ ONLY: no sales, journals, account mappings, stock or opening balances changed.')


if __name__ == '__main__':
    main()
