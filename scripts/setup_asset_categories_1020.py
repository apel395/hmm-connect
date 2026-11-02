"""Configure PPh group categories; retire proven script defaults. Default is a rolled-back preview."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import text
from app.models.fixed_asset import FixedAssetCategory, FixedAsset
from app.models.amortization import Amortization
from app.models.chart_of_account import ChartOfAccount
from app.schemas.fixed_asset import CategoryInput
from app.services.fixed_asset_service import FixedAssetService
from app.services.audit import record_audit
from types import SimpleNamespace

# Do not classify utensils or use operating-equipment COA as automatic PPE.
POLICIES = [
    ('MMH-LAND', 'Tanah', '100-600-100', None),
    ('MMH-BUILDING', 'Bangunan', '100-600-101', '100-800-100'),
    ('MMH-MECHANICAL', 'Mekanikal dan Elektrikal', '100-600-102', '100-800-101'),
    ('MMH-VEHICLE', 'Kendaraan', '100-600-103', '100-800-102'),
    ('MMH-FFE', 'Furniture, Fixtures and Equipment', '100-600-104', '100-800-103'),
    ('MMH-INVENTARIS', 'Inventaris', '100-600-105', '100-800-104'),
    ('MMH-OTHER-999', 'Asset Tetap Lainnya', '100-600-999', '100-800-999'),
]


def setup(db, create=True):
    if db.bind.dialect.name == 'postgresql': db.execute(text('SELECT pg_advisory_xact_lock(20261020, 48)'))
    from app.services.asset_category_policy import setup_pph_categories
    report = setup_pph_categories(db, create=create)
    result = report['categories']
    accounts = {a.account_number: a for a in db.query(ChartOfAccount).all()}
    accounts_by_id = {a.id: a.account_number for a in accounts.values()}
    reviews = [{'kind': 'LEGACY_CATEGORY_MAPPING', 'id': a.id, 'name': a.name, 'account': accounts_by_id.get(a.asset_account_id)} for a in db.query(FixedAssetCategory).all() if a.code == 'MMH-OTHER' and a.asset_account_id == getattr(accounts.get('100-600-105'), 'id', None)]
    reviews += [{'kind': 'CATEGORY', 'id': a.id, 'name': a.name, 'life': a.default_useful_life_months}
        for a in db.query(FixedAssetCategory).all() if a.is_depreciable and (not a.default_useful_life_months or a.default_useful_life_months < 48)]
    reviews += [{'kind': 'FIXED_ASSET', 'id': a.id, 'name': a.asset_name, 'life': a.useful_life_months}
        for a in db.query(FixedAsset).all() if a.depreciation_method != 'NONE' and a.status != 'PENDING_REGISTRATION' and (not a.useful_life_months or a.useful_life_months < 48)]
    reviews += [{'kind': 'AMORTIZATION', 'id': a.id, 'name': a.name, 'life': a.useful_life_months}
        for a in db.query(Amortization).all() if a.useful_life_months < 48]
    return {**report, 'existing_policy_reviews': reviews}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    from app.core.database import SessionLocal
    with SessionLocal() as db:
        report = setup(db)
        if args.apply: db.commit()
        else: db.rollback()
    print(json.dumps({'mode': 'APPLY' if args.apply else 'DRY_RUN', **report}, indent=2))
    print('COMMITTED PPh categories and replacement of proven script defaults. Existing assets, schedules, journals and balances unchanged.' if args.apply else 'DRY RUN: changes rolled back.')


if __name__ == '__main__': main()
