"""Read-only validation of POS PBJT schema and the existing liability COA."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import json
from fastapi import HTTPException
from sqlalchemy import inspect, text
from app.core.database import SessionLocal
from app.services.pos_tax import pbjt_account


def main():
    with SessionLocal() as db:
        db.execute(text('SET TRANSACTION READ ONLY'))
        columns = {c['name'] for c in inspect(db.connection()).get_columns('sales_transaction_lines')}
        result = {'schema': {c: c in columns for c in ('tax_type', 'tax_account_id')}}
        try:
            account = pbjt_account(db)
            result['pbjt_account'] = {'id':account.id,'code':account.account_number,'name':account.account_name}
        except HTTPException as exc:
            result['pbjt_account_error'] = exc.detail
        result['pbjt_sell_items'] = [dict(r) for r in db.execute(text("SELECT code,name,pbjt_rate,selling_price FROM products WHERE item_type='SELL' AND is_active AND pbjt_rate>0 ORDER BY code")).mappings()]
        print(json.dumps(result, default=str, indent=2))
        db.rollback()
    print('READ ONLY: no accounts, sales, journals, GL, stock or opening balances changed.')


if __name__ == '__main__':
    main()
