#!/usr/bin/env python3
"""Seed classified BUY item identities from the reviewed source; dry-run by default.

Known names use explicit reviewed catalog/COA mappings; tax remains REVIEW_REQUIRED.
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
    from resiping_buy_catalog import BUY_GROUPS
    for item in candidates:
        profile=item['new_product']
        if profile['group_name'] not in BUY_GROUPS or profile['group_code']==GROUP_CODE:
            raise ValueError('Pending catalog creation disabled. Classify the source item before seeding.')
        group=db.query(ItemGroup).filter(ItemGroup.code==profile['group_code']).one_or_none()
        if not group or not group.is_active or group.item_type not in ('BUY','ITEM') or group.name!=profile['group_name']:
            raise ValueError('Approved BUY group changed')
        if group.item_type=='ITEM':
            if db.query(Product).filter(Product.group_code==group.code,Product.item_type!='BUY').first():
                raise ValueError('Legacy group shared with non-BUY products')
            group.item_type='BUY'
        subgroup=db.query(ItemSubgroup).filter(ItemSubgroup.code==profile['subgroup_code']).one_or_none()
        if not subgroup and group.name=='BEVERAGE' and profile['subgroup_name']=='SYRUP':
            subgroup=ItemSubgroup(code=profile['subgroup_code'],name='SYRUP',group_id=group.id,is_active=True)
            db.add(subgroup);db.flush()
        if not subgroup or not subgroup.is_active or subgroup.group_id!=group.id or subgroup.name!=profile['subgroup_name']:
            raise ValueError('Existing BUY subgroup changed')
    inserted = []
    for item in candidates:
        product = Product(**item['new_product'])
        db.add(product);db.flush()
        record_audit(db,user,'RESIPING_BUY_ITEM_CREATED','PRODUCT',f'Create classified BUY item {product.code}',
            entity_id=product.id,after_data={**item['new_product'],'id':product.id},
            details={'module':'Item Master','source_sha256':report['source_sha256'],
                     'source_rows':json.loads(json.dumps(item['source_rows'],default=str)),'classification_required':False,'tax_review_required':True})
        inserted.append({'id':product.id,'code':product.code,'name':product.name})
    return inserted



def classified_seed_plan(db, report, products):
    """Known source names receive approved catalog/COA before insertion; unknowns defer."""
    from app.models.item_group import ItemGroup
    from app.models.item_subgroup import ItemSubgroup
    from app.models.chart_of_account import ChartOfAccount
    from classify_resiping_items import MANIFEST, desired_profile
    from resiping_buy_catalog import existing_subgroup
    from types import SimpleNamespace
    manifest=json.loads(MANIFEST.read_text())
    rules={r['name']:r for r in manifest['items']}
    report=seed_plan(report,products)
    groups=db.query(ItemGroup).all();subgroups=db.query(ItemSubgroup).all()
    accounts=db.query(ChartOfAccount).all()
    for item in report['items']:
        if 'new_product' not in item:continue
        rule=rules.get(item['name'])
        if not rule or item['units']!=rule['units']:
            item.pop('new_product');item['match_status']='CLASSIFICATION_REVIEW';continue
        matches=[g for g in groups if g.name==rule['group'] and g.is_active and g.item_type in ('BUY','ITEM')]
        if len(matches)!=1:raise ValueError(f'Approved BUY family {rule["group"]} not uniquely configured')
        group=matches[0]
        if rule['subgroup']=='SYRUP':
            matched=[s for s in subgroups if s.group_id==group.id and s.name=='SYRUP' and s.is_active]
            if len(matched)>1:raise ValueError('Duplicate SYRUP subgroup')
            if matched:subgroup=matched[0]
            else:
                code='RC'+sha256('BEVERAGE|SYRUP'.encode()).hexdigest()[:8].upper()
                if any(s.code==code for s in subgroups):raise ValueError('SYRUP code collision')
                subgroup=SimpleNamespace(code=code,name='SYRUP',group_id=group.id)
        else:subgroup=existing_subgroup(subgroups,group,rule['subgroup'])
        item['new_product'].update(desired_profile(rule,group,subgroup,accounts))
        item['match_status']='NEW_CLASSIFIED_BUY_ITEM'
    report['db_matches']=dict(Counter(i['match_status'] for i in report['items']))
    report['new_master_items']=sum('new_product' in i for i in report['items'])
    return report


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
            report = classified_seed_plan(db,report,products)
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
            print('COMMITTED classified BUY items and audit records only.' if args.apply else 'DRY RUN: no writes. --apply creates eligible classified BUY items; no BUYPEND group.')
        except Exception:
            db.rollback();raise


if __name__=='__main__':
    main()
