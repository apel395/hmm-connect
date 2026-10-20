"""Configure missing MMH fixed asset categories. Default is a rolled-back preview."""
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
    ('MMH-OTHER', 'Aset Tetap Lainnya', '100-600-105', '100-800-104'),
]


def setup(db, create=True):
    if db.bind.dialect.name == 'postgresql': db.execute(text('SELECT pg_advisory_xact_lock(20261020, 48)'))
    accounts = {a.account_number: a for a in db.query(ChartOfAccount).all()}
    actor = SimpleNamespace(id=None, full_name='EC2 asset category setup', roles=[])
    result = []
    for code, name, asset_code, accumulated_code in POLICIES:
        existing = db.query(FixedAssetCategory).filter_by(code=code).first()
        if existing:
            result.append({'code': code, 'action': 'EXISTING_UNCHANGED', 'life': existing.default_useful_life_months}); continue
        required = [asset_code] + ([accumulated_code, '700-500-133'] if accumulated_code else [])
        missing = [c for c in required if c not in accounts]
        if missing:
            result.append({'code': code, 'action': 'REVIEW_MISSING_COA', 'accounts': missing}); continue
        value = CategoryInput(code=code, name=name, asset_account_id=accounts[asset_code].id,
            is_depreciable=bool(accumulated_code), default_useful_life_months=48 if accumulated_code else None,
            accumulated_depreciation_account_id=accounts[accumulated_code].id if accumulated_code else None,
            depreciation_expense_account_id=accounts['700-500-133'].id if accumulated_code else None)
        FixedAssetService(db).validate_accounts(value)
        if create:
            category = FixedAssetService(db).create_category(value)
            record_audit(db, actor, 'ASSET_CATEGORY_CREATED', 'FIXED_ASSET_CATEGORY', f'Create {code}', entity_id=category.id,
                after_data=value.model_dump(mode='json'), details={'batch': 'ASSET_POLICY_20261020', 'accounting_created': False})
        result.append({'code': code, 'action': 'CREATE' if create else 'AVAILABLE', 'life': value.default_useful_life_months})
    reviews = [{'kind': 'CATEGORY', 'id': a.id, 'name': a.name, 'life': a.default_useful_life_months}
        for a in db.query(FixedAssetCategory).all() if a.is_depreciable and (not a.default_useful_life_months or a.default_useful_life_months < 48)]
    reviews += [{'kind': 'FIXED_ASSET', 'id': a.id, 'name': a.asset_name, 'life': a.useful_life_months}
        for a in db.query(FixedAsset).all() if a.depreciation_method != 'NONE' and a.status != 'PENDING_REGISTRATION' and (not a.useful_life_months or a.useful_life_months < 48)]
    reviews += [{'kind': 'AMORTIZATION', 'id': a.id, 'name': a.name, 'life': a.useful_life_months}
        for a in db.query(Amortization).all() if a.useful_life_months < 48]
    return {'categories': result, 'existing_policy_reviews': reviews}


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
    print('COMMITTED missing categories and audit only. Existing assets, schedules, journals and balances unchanged.' if args.apply else 'DRY RUN: changes rolled back.')


if __name__ == '__main__': main()
