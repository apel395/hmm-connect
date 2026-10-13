"""Read-only schema and policy evidence for the fixed asset deployment."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import inspect, text
from app.core.database import SessionLocal


def main():
    with SessionLocal() as db:
        db.execute(text('SET TRANSACTION READ ONLY'))
        inspector=inspect(db.connection())
        expected={'fixed_asset_categories':{'is_depreciable'},'fixed_assets':{'quantity'},'fixed_asset_movements':{'journal_entry_id'}}
        for table,fields in expected.items():
            missing=fields-{c['name'] for c in inspector.get_columns(table)}
            if missing:raise SystemExit(f'Migration required: {table} missing {sorted(missing)}')
        categories={c['name']:c for c in inspector.get_columns('fixed_asset_categories')}
        for field in ('default_useful_life_months','accumulated_depreciation_account_id','depreciation_expense_account_id'):
            if not categories[field]['nullable']:raise SystemExit(f'Migration required: {field} must be nullable')
        result={
            'schema':'OK',
            'migration':db.execute(text('SELECT version_num FROM alembic_version')).scalars().all(),
            'categories':[dict(r) for r in db.execute(text('SELECT code,name,is_depreciable,default_useful_life_months,asset_account_id,accumulated_depreciation_account_id,depreciation_expense_account_id FROM fixed_asset_categories ORDER BY code')).mappings()],
            'register_statuses':[dict(r) for r in db.execute(text('SELECT status,count(*) AS records FROM fixed_assets GROUP BY status ORDER BY status')).mappings()],
            'policy_reviews':[dict(r) for r in db.execute(text("SELECT a.asset_number,a.status,c.code,a.depreciation_method FROM fixed_assets a LEFT JOIN fixed_asset_categories c ON c.id=a.asset_category_id WHERE a.status <> 'PENDING_REGISTRATION' AND ((c.is_depreciable=false AND a.depreciation_method <> 'NONE') OR (c.is_depreciable=true AND a.depreciation_method='NONE'))")).mappings()],
            'legacy_amortization_remainders':[dict(r) for r in db.execute(text("SELECT id,amortization_number,months_posted,useful_life_months,net_book_value FROM amortizations WHERE months_posted >= useful_life_months AND net_book_value <> 0")).mappings()],
        }
        print(json.dumps(result,indent=2,default=str));db.rollback()
    print('READ ONLY: no categories, assets, journals, GL or opening balances changed.')

if __name__=='__main__':main()
