"""Reclassify all unvalued Hotel utensil registrations; preview by default.

Actual item IDs, names and account links are read under lock. Any valuation,
stock, source-document or depreciation evidence aborts the whole transaction.
"""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.product import Product
from app.models.fixed_asset import FixedAsset
from app.models.chart_of_account import ChartOfAccount
from app.services.item_asset_policy import is_utensil
from app.services.item_code import lock_item_creation
from scripts.reclassify_hotel_utensils_1020 import repair


def cleanup(db):
    lock_item_creation(db)
    products = db.query(Product).filter(Product.catalog_type == 'HOTEL', Product.item_type == 'BUY',
        Product.inventory_treatment == 'FIXED_ASSET').order_by(Product.id).with_for_update().all()
    targets = []
    for p in products:
        if not is_utensil(p): continue
        assets = db.query(FixedAsset).filter_by(product_id=p.id).with_for_update().all()
        account = db.get(ChartOfAccount, p.asset_account_id)
        if len(assets) != 1 or not account:
            raise ValueError(f'Utensil {p.id} has missing/multiple asset or COA links; inspect before cleanup')
        targets.append((p.id, p.code, p.name, assets[0].id, account.account_number))
    return repair(db, targets=tuple(targets))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    from app.core.database import SessionLocal
    with SessionLocal() as db:
        result = cleanup(db)
        if args.apply: db.commit()
        else: db.rollback()
    print(json.dumps({'mode': 'APPLY' if args.apply else 'DRY_RUN', **result}, indent=2))
    print('COMMITTED Item Master reclassification and removal of empty pending asset records only.' if args.apply else 'DRY RUN: changes rolled back.')


if __name__ == '__main__': main()
