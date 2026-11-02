"""Read-only schema and COA check; does not create categories or fiscal profiles."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import inspect, select
from app.core.database import SessionLocal
from app.models.chart_of_account import ChartOfAccount
from app.models.fixed_asset import FixedAssetCategory, FixedAsset, FixedAssetFiscalProfile
from app.services.asset_account_policy import ASSET_ACCOUNTS, DEPRECIATION_EXPENSE


def main():
    with SessionLocal() as db:
        codes=set(ASSET_ACCOUNTS)|{v[1] for v in ASSET_ACCOUNTS.values() if v[1]}|{DEPRECIATION_EXPENSE}
        accounts={a.account_number:a for a in db.query(ChartOfAccount).filter(ChartOfAccount.account_number.in_(codes)).all()}
        table=inspect(db.get_bind()).has_table('fixed_asset_fiscal_profiles')
        linen_ids=select(ChartOfAccount.id).where(ChartOfAccount.account_number=='100-900-100')
        report={'mode':'READ_ONLY','schema':'OK' if table else 'MIGRATION_REQUIRED',
                'accounts':[{'code':code,'name':accounts[code].account_name if code in accounts else None,
                             'active_posting': bool(code in accounts and accounts[code].is_active and accounts[code].is_posting)} for code in sorted(codes)],
                'fiscal_profiles':db.query(FixedAssetFiscalProfile).count() if table else None,
                'legacy_linen_assets':[{'id':a.id,'number':a.asset_number,'status':a.status,'cost':str(a.acquisition_cost) if a.acquisition_cost is not None else None} for a in db.query(FixedAsset).filter(FixedAsset.asset_account_id.in_(linen_ids)).all()],
                'legacy_other_categories':[{'id':c.id,'name':c.name,'asset_account_id':c.asset_account_id} for c in db.query(FixedAssetCategory).filter(FixedAssetCategory.code=='MMH-OTHER').all()]}
        print(json.dumps(report,indent=2))
        db.rollback()
    print('READ ONLY: no categories, items, assets, fiscal profiles, stock, GL or opening balances changed.')


if __name__=='__main__': main()
