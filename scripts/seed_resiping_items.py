#!/usr/bin/env python3
"""Seed new BUY item identities before classification; dry-run by default.

New items are explicitly REVIEW_REQUIRED with no accounting or tax decision.
Existing BUY/SELL products and all transactions stay unchanged. Similar names,
inactive/ambiguous matches and multiple-unit rows are deferred for review.
"""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from prepare_resiping_item_seed import load_source, match_existing

GROUP_CODE = 'BUYPEND'
SUBGROUP_CODE = 'BUYPEND-1'


def seed_plan(report, products):
    for item in report['items']: item.pop('new_product', None)
    report['db_matches'] = match_existing(report['items'],products)
    occupied = {p['code'] for p in products}
    for item in report['items']:
        if item['match_status'] != 'NEW_BUY_ITEM_REQUIRES_CLASSIFICATION':
            continue
        code = 'RBI-' + sha256(item['name'].encode()).hexdigest()[:16].upper()
        if code in occupied:
            item['match_status'] = 'PRODUCT_CODE_CONFLICT'; continue
        if len(item['name']) > 150 or len(item['units'][0]) > 20:
            item['match_status'] = 'FIELD_LENGTH_REVIEW'; continue
        item['new_product'] = {'code':code,'name':item['name'],'item_type':'BUY',
            'uom':item['units'][0],'usage_uom':item['units'][0],'conversion':1,
            'group_code':GROUP_CODE,'group_name':'BUY — PENDING CLASSIFICATION',
            'subgroup_code':SUBGROUP_CODE,'subgroup_name':'PENDING CLASSIFICATION',
            'inventory_treatment':'REVIEW_REQUIRED','tax_category':'REVIEW_REQUIRED',
            'inventory_account_id':None,'purchase_account_id':None,'cogs_account_id':None,
            'asset_account_id':None,'is_active':True,'is_taxable':False,'tax_rate':0,
            'tax_reason':'Pending invoice-backed tax classification; false flag is not a tax exemption decision'}
        occupied.add(code)
    report['database_checked'] = True
    report['db_matches'] = dict(Counter(item['match_status'] for item in report['items']))
    report['new_master_items'] = sum('new_product' in item for item in report['items'])
    return report


def insert_items(db, report, user=None):
    from app.models.item_group import ItemGroup
    from app.models.item_subgroup import ItemSubgroup
    from app.models.product import Product
    from app.services.audit import record_audit
    candidates = [item for item in report['items'] if 'new_product' in item]
    if not candidates:
        return []
    group = db.query(ItemGroup).filter(ItemGroup.code==GROUP_CODE).first()
    if group and (group.item_type != 'BUY' or not group.is_active or group.name != 'BUY — PENDING CLASSIFICATION'):
        raise ValueError('Pending BUY group conflicts with existing catalog')
    if not group:
        group = ItemGroup(code=GROUP_CODE,name='BUY — PENDING CLASSIFICATION',item_type='BUY',is_active=True)
        db.add(group);db.flush()
    subgroup = db.query(ItemSubgroup).filter(ItemSubgroup.code==SUBGROUP_CODE).first()
    if subgroup and (subgroup.group_id != group.id or not subgroup.is_active or subgroup.name != 'PENDING CLASSIFICATION'):
        raise ValueError('Pending BUY subgroup conflicts with existing catalog')
    if not subgroup:
        subgroup = ItemSubgroup(code=SUBGROUP_CODE,name='PENDING CLASSIFICATION',group_id=group.id,is_active=True)
        db.add(subgroup);db.flush()
    inserted = []
    for item in candidates:
        product = Product(**item['new_product'])
        db.add(product);db.flush()
        record_audit(db,user,'RESIPING_BUY_ITEM_CREATED','PRODUCT',f'Create pending BUY item {product.code}',
            entity_id=product.id,after_data={**item['new_product'],'id':product.id},
            details={'module':'Item Master','source_sha256':report['source_sha256'],
                     'source_rows':json.loads(json.dumps(item['source_rows'],default=str)),'classification_required':True})
        inserted.append({'id':product.id,'code':product.code,'name':product.name})
    return inserted


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--file',type=Path)
    source.add_argument('--drive-id',help='Public Google Drive Excel file ID')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--actor-id',type=int)
    args = parser.parse_args()
    report = load_source(args.file,args.drive_id)
    from sqlalchemy import text
    from app.core.database import SessionLocal
    from app.models.product import Product
    from app.models.user import User
    with SessionLocal() as db:
        try:
            if not args.apply:
                db.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
            db.execute(text("SET LOCAL lock_timeout='5s'"))
            db.execute(text("SET LOCAL statement_timeout='60s'"))
            if args.apply:
                db.execute(text('SELECT pg_advisory_xact_lock(484006,260)'))
                db.execute(text('LOCK TABLE products,item_groups,item_subgroups IN SHARE ROW EXCLUSIVE MODE'))
            user = db.get(User,args.actor_id) if args.actor_id else None
            if args.actor_id and not user:
                raise ValueError('Audit actor does not exist')
            products = [{'id':p.id,'code':p.code,'name':p.name,'item_type':p.item_type,
                         'is_active':p.is_active,'uom':p.uom} for p in db.query(Product).all()]
            report = seed_plan(report,products)
            report['mode'] = 'APPLY' if args.apply else 'DRY_RUN'
            if args.apply:
                report['inserted_items'] = insert_items(db,report,user)
            # Validate report destination before committing any transaction.
            args.output.write_text(json.dumps(report,indent=2,default=str,ensure_ascii=False)+'\n')
            if args.apply:
                db.commit()
            else:
                db.rollback()
            print(json.dumps({key:value for key,value in report.items() if key not in ('items','excluded_rows','review_rows','inserted_items')},indent=2,default=str,ensure_ascii=False))
            print(f'Full item plan: {args.output}')
            print('COMMITTED pending BUY items and audit records only.' if args.apply else 'DRY RUN: no writes. --apply creates eligible new BUY items pending classification.')
        except Exception:
            db.rollback();raise


if __name__=='__main__':
    main()
