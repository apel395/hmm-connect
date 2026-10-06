#!/usr/bin/env python3
"""Classify the audited 291-item BUY seed from the exact RESIPING workbook.

Dry-run by default. Explicit per-name manifest; no fuzzy name classification.
Only unused, unchanged products from the creation audit batch are updated.
Tax, document lines, warehouse balances, movements and journals are untouched.
"""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from prepare_resiping_item_seed import load_source, normalized

MANIFEST = ROOT / 'scripts/resiping_item_classification_20261006.json'
FIELDS = ('code','name','item_type','uom','usage_uom','conversion','is_active',
          'group_code','group_name','subgroup_code','subgroup_name',
          'inventory_treatment','inventory_account_id','purchase_account_id',
          'cogs_account_id','asset_account_id','tax_category','is_taxable','tax_rate')
ACCOUNT_PROFILES = {'FOOD': ('100-300-100','500-100-100'),
                    'BEVERAGE': ('100-300-500','500-100-102'),
                    'MATERIAL': ('100-300-700',None)}


def verify_source(source, manifest):
    if source['source_sha256'] != manifest['source_sha256']:
        raise ValueError('Workbook differs from the reviewed seed snapshot. Use /tmp/resiping-seed-20261006.xlsm from the original seed, or review the new workbook first.')
    names = {x['name']: x['units'] for x in source['items']}
    rules = {x['name']: x for x in manifest['items']}
    if len(rules) != len(manifest['items']) or set(names) != set(rules):
        raise ValueError('Workbook names differ from the explicit classification manifest')
    for name, rule in rules.items():
        if names[name] != rule['units'] or rule['group'] not in ACCOUNT_PROFILES or rule['treatment'] not in ('STOCK','DIRECT_USE'):
            raise ValueError(f'Invalid classification or source units: {name}')
    return rules


def validate_identity(product, created, rule):
    expected_code = 'RBI-' + sha256(rule['name'].encode()).hexdigest()[:16].upper()
    if (product.item_type != 'BUY' or product.name != rule['name'] or product.code != expected_code
            or product.uom not in rule['units'] or len(rule['units']) != 1):
        raise ValueError(f'Item identity or unit changed: {product.id} {product.name}')
    for field in ('code','name','item_type','uom','usage_uom','conversion','is_active','tax_category','is_taxable','tax_rate'):
        actual = getattr(product, field)
        expected = created.get(field)
        if field in ('conversion','tax_rate'):
            from decimal import Decimal
            matches = Decimal(str(actual)) == Decimal(str(expected))
        else:
            matches = actual == expected
        if not matches:
            raise ValueError(f'Item {product.id} field {field} changed since seed; review before classification')


def resolve_account(accounts, number):
    if number is None:
        return None
    matches = [a for a in accounts if a.account_number == number]
    if len(matches) != 1:
        raise ValueError(f'Posting account {number} is not uniquely configured')
    a = matches[0]
    required = 'ASSET' if number.startswith('100-') else 'EXPENSE'
    if not a.is_active or not a.is_posting or a.account_type != required or a.normal_balance != 'DEBIT':
        raise ValueError(f'Posting account {number} is not an active debit {required} account')
    return a.id


def desired_profile(rule, group, subgroup, accounts):
    inv, expense = ACCOUNT_PROFILES[rule['group']]
    inv_id = resolve_account(accounts, inv)
    expense_id = resolve_account(accounts, expense)
    direct = rule['treatment'] == 'DIRECT_USE'
    if direct and expense_id is None:
        raise ValueError('Direct-use expense account must be explicitly configured')
    return {'group_code':group.code,'group_name':group.name,
            'subgroup_code':subgroup.code,'subgroup_name':subgroup.name,
            'inventory_treatment':rule['treatment'],
            'inventory_account_id':None if direct else inv_id,
            'purchase_account_id':expense_id if direct else None,
            'cogs_account_id':None if direct else expense_id,'asset_account_id':None}


def snapshot(product):
    return json.loads(json.dumps({f:getattr(product,f) for f in FIELDS}, default=str))


def classify_batch(db, source, manifest, apply=False, user=None):
    from sqlalchemy import text
    from app.models.product import Product
    from app.models.audit_log import AuditLog
    from app.models.item_group import ItemGroup
    from app.models.item_subgroup import ItemSubgroup
    from app.models.chart_of_account import ChartOfAccount
    from app.services.audit import record_audit
    rules = verify_source(source, manifest)
    logs = db.query(AuditLog).filter(AuditLog.action=='RESIPING_BUY_ITEM_CREATED',AuditLog.entity_type=='PRODUCT').all()
    batch = [a for a in logs if (a.details or {}).get('source_sha256') == manifest['source_sha256']]
    if len(batch) != manifest['expected_batch_count'] or len({a.entity_id for a in batch}) != len(batch):
        raise ValueError(f'Expected exactly {manifest["expected_batch_count"]} unique creation audits, found {len(batch)}')
    ids = [a.entity_id for a in batch]
    query = db.query(Product).filter(Product.id.in_(ids))
    products = {p.id:p for p in (query.with_for_update().all() if apply else query.all())}
    if len(products) != len(ids):
        raise ValueError('A seeded product is missing')
    groups = db.query(ItemGroup).all()
    subgroups = db.query(ItemSubgroup).all()
    accounts = db.query(ChartOfAccount).all()
    from types import SimpleNamespace
    group_cache = {}
    subgroup_cache = {}
    catalog_changes = []
    occupied_codes = {s.code for s in subgroups}
    for name in sorted({rules[products[i].name]['group'] for i in ids if products[i].name in rules}):
        candidates = [g for g in groups if normalized(g.name)==name and g.is_active and g.item_type in ('BUY','ITEM')]
        if len(candidates)!=1:
            raise ValueError(f'Active BUY group {name} not uniquely configured')
        group = candidates[0]
        if group.item_type=='ITEM':
            if db.query(Product).filter(Product.group_code==group.code,Product.item_type!='BUY').first():
                raise ValueError(f'Legacy group {name} is shared with non-BUY items')
            catalog_changes.append({'group':name,'action':'normalize legacy ITEM group to BUY'})
        group_cache[name] = group
    # Plan catalog without writes; all item validations run before applying.
    for rule in [rules[products[i].name] for i in ids if products[i].name in rules]:
        if rule['group'] not in group_cache:
            continue
        key=(rule['group'],rule['subgroup'])
        if key in subgroup_cache:
            continue
        group=group_cache[rule['group']]
        matches=[s for s in subgroups if s.group_id==group.id and normalized(s.name)==rule['subgroup'] and s.is_active]
        if len(matches)>1:
            raise ValueError(f'Duplicate active subgroup: {key}')
        if matches:
            subgroup_cache[key]=matches[0]
        else:
            # Codes fit String(10), scoped to BUY parent; no dependence on product prefix.
            code='RC'+sha256(('|'.join(key)).encode()).hexdigest()[:8].upper()
            if code in occupied_codes:
                raise ValueError(f'Subgroup code collision: {code}')
            occupied_codes.add(code)
            subgroup_cache[key]=SimpleNamespace(code=code,name=rule['subgroup'],group_id=group.id)
            catalog_changes.append({'group':rule['group'],'subgroup':rule['subgroup'],'code':code,'action':'create subgroup'})
    plan=[]
    for log in sorted(batch,key=lambda a:a.entity_id):
        p=products[log.entity_id]
        rule=rules.get(p.name)
        if not rule:
            raise ValueError(f'Seeded item missing from source manifest: {p.name}')
        created=log.after_data or {}
        validate_identity(p,created,rule)
        group=group_cache[rule['group']]
        subgroup=subgroup_cache[(rule['group'],rule['subgroup'])]
        desired=desired_profile(rule,group,subgroup,accounts)
        before=snapshot(p)
        if all(getattr(p,k)==v for k,v in desired.items()):
            status='ALREADY_CLASSIFIED'
        else:
            for field in desired:
                if getattr(p,field)!=created.get(field):
                    raise ValueError(f'Item {p.id} profile changed since seed; refusing overwrite of {field}')
            # Any existing usage needs a separate historical correction, not master-only edits.
            for table in ('inventory','stock_movements','goods_receipt_items','supplier_invoice_lines'):
                if db.execute(text(f'SELECT 1 FROM {table} WHERE product_id=:pid LIMIT 1'),{'pid':p.id}).first():
                    raise ValueError(f'Item {p.id} already used in {table}; review its history before accounting classification')
            status='CLASSIFY'
        plan.append({'id':p.id,'code':p.code,'name':p.name,'status':status,'reason':rule['reason'],
                     'before':before,'after':{**before,**desired}})
    report={'mode':'APPLY' if apply else 'DRY_RUN','source_sha256':source['source_sha256'],
            'batch_items':len(plan),'counts':dict(Counter(x['status'] for x in plan)),
            'classification_counts':dict(Counter(f'{x["after"]["group_name"]} / {x["after"]["inventory_treatment"]}' for x in plan)),
            'catalog_changes':catalog_changes,'tax_policy':manifest['tax_policy'],'items':plan}
    if apply and any(x['status']=='CLASSIFY' for x in plan):
        for group in group_cache.values():
            if group.item_type=='ITEM':
                before={'id':group.id,'code':group.code,'item_type':group.item_type}
                group.item_type='BUY'
                record_audit(db,user,'RESIPING_BUY_GROUP_NORMALIZED','ITEM_GROUP',f'Normalize BUY group {group.name}',entity_id=group.id,before_data=before,after_data={**before,'item_type':'BUY'})
        for key,s in subgroup_cache.items():
            if not isinstance(s,ItemSubgroup):
                new=ItemSubgroup(code=s.code,name=s.name,group_id=s.group_id,is_active=True)
                db.add(new);db.flush()
                record_audit(db,user,'RESIPING_BUY_SUBGROUP_CREATED','ITEM_SUBGROUP',f'Create BUY subgroup {s.name}',entity_id=new.id,after_data={'code':s.code,'name':s.name,'group_id':s.group_id})
        for row in plan:
            if row['status']!='CLASSIFY':
                continue
            p=products[row['id']]
            for field in ('group_code','group_name','subgroup_code','subgroup_name','inventory_treatment','inventory_account_id','purchase_account_id','cogs_account_id','asset_account_id'):
                setattr(p,field,row['after'][field])
            record_audit(db,user,'RESIPING_BUY_ITEM_CLASSIFIED','PRODUCT',f'Classify seeded BUY item {p.code}',entity_id=p.id,before_data=row['before'],after_data=row['after'],details={'source_sha256':source['source_sha256'],'source':'RESIPING ITEM_ENTRY 2026 rows','reason':row['reason'],'tax_changed':False})
        db.flush()
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    src=parser.add_mutually_exclusive_group(required=True)
    src.add_argument('--file',type=Path)
    src.add_argument('--drive-id')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--actor-id',type=int)
    args=parser.parse_args()
    source=load_source(args.file,args.drive_id)
    manifest=json.loads(MANIFEST.read_text())
    verify_source(source,manifest)  # Validate workbook before opening DB.
    from sqlalchemy import text
    from app.core.database import SessionLocal
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
            user=db.get(User,args.actor_id) if args.actor_id else None
            if args.actor_id and not user:
                raise ValueError('Audit actor does not exist')
            report=classify_batch(db,source,manifest,args.apply,user)
            args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False,default=str)+'\n')
            if args.apply:
                db.commit()
            else:
                db.rollback()
            print(json.dumps({k:v for k,v in report.items() if k not in ('items','catalog_changes')},indent=2))
            print(f'Full classification report: {args.output}')
            print('COMMITTED item master classification and audit records only.' if args.apply else 'DRY RUN: no writes. Use --apply to classify this batch.')
        except Exception:
            db.rollback()
            raise

if __name__=='__main__':
    main()
