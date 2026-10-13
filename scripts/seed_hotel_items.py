"""Seed the fully classified HOTEL BUY subset of invlistofgoods.xls.

Dry run by default. Unresolved rows remain in the report, not in a pending group.
Only Product and audit records are inserted. No existing master is updated.
"""
import argparse
from collections import Counter
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.prepare_hotel_items import SOURCE, build_plan, normalize, read_source

SOURCE_SHA = 'a9d0e58b3fa1bacbe4d5cfcdcb96e1d9cfef003343979b0c71d1fd623f2ed96a'
INVENTORY_COA = {'FOOD': '100-300-100', 'BEVERAGE': '100-300-500'}
INFORMATIONAL = {'NEGATIVE_LEGACY_EXPENSE_REFERENCE'}


def seed_plan(source, products, groups, subgroups, accounts):
    if source.get('source_sha256') != SOURCE_SHA:
        raise ValueError('Source workbook changed; prepare and inspect the new version first')
    rows = build_plan(source, products, groups, subgroups, database_checked=True)
    for row in rows:
        if not normalize(row['unit']): row['issues'].append('UNIT_MISSING')
        if len(row['name'].strip()) > 150 or len(row['unit'].strip()) > 20:
            row['issues'].append('FIELD_LENGTH_REVIEW')
        if row['inventory_treatment'] != 'STOCK' or row['group'] not in INVENTORY_COA:
            row['issues'].append('CLASSIFICATION_NOT_FINAL')
        account_number = INVENTORY_COA.get(row['group'])
        matched = [a for a in accounts if a['account_number'] == account_number
                   and a['is_active'] and a['is_posting'] and a['account_type'] == 'ASSET'
                   and a['normal_balance'] == 'DEBIT']
        if account_number is not None and len(matched) != 1:
            row['issues'].append('INVENTORY_COA_NOT_UNIQUE')
        try:
            cost = Decimal(str(row['purchase']))
            if not cost.is_finite() or cost < 0 or cost >= Decimal('10000000000'):
                raise ValueError('Invalid purchase reference')
            cost = cost.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
            if cost >= Decimal('10000000000'): raise ValueError('Purchase reference too large')
        except (InvalidOperation, ValueError):
            row['issues'].append('PURCHASE_REFERENCE_REVIEW')
            cost = Decimal('0')
        blocking = set(row['issues']) - INFORMATIONAL
        if row['existing_hotel_ids']:
            # A name match never authorizes updating or moving an existing product.
            row['seed_status'] = 'EXISTING_HOTEL_ITEM' if len(row['existing_hotel_ids']) == 1 else 'REVIEW'
        elif blocking:
            row['seed_status'] = 'REVIEW'
        else:
            group = next(g for g in groups if g['id'] == row['group_id'])
            subgroup = next(s for s in subgroups if s['id'] == row['subgroup_id'])
            row['new_product'] = {
                'name': row['name'].strip(), 'catalog_type': 'HOTEL', 'item_type': 'BUY',
                'group_code': group['code'], 'group_name': group['name'],
                'subgroup_code': subgroup['code'], 'subgroup_name': subgroup['name'],
                'uom': row['unit'].strip(), 'usage_uom': row['unit'].strip(), 'conversion': 1,
                'inventory_treatment': 'STOCK', 'inventory_account_id': matched[0]['id'],
                'purchase_account_id': None, 'cogs_account_id': None, 'asset_account_id': None,
                'cost_price': str(cost), 'reference_cost_method': 'LAST_PURCHASE',
                'selling_price': '0', 'tax_category': 'REVIEW_REQUIRED',
                'is_taxable': False, 'tax_rate': '0',
                'tax_reason': 'Legacy Item Master has no invoice tax evidence; not a tax exemption decision',
                'description': f"Hotel legacy master reference: {source['sheet']}, row {row['source_row']}, code {row['legacy_code']}",
                'is_active': True,
            }
            row['seed_status'] = 'CREATE'
    return rows


def database_snapshot(db):
    from sqlalchemy import text
    products = [dict(r) for r in db.execute(text('SELECT id,code,name,uom,catalog_type,item_type FROM products')).mappings()]
    groups = [dict(r) for r in db.execute(text("SELECT id,name,code FROM item_groups WHERE is_active AND item_type IN ('BUY','ITEM')")).mappings()]
    subgroups = [dict(r) for r in db.execute(text('SELECT id,name,code,group_id FROM item_subgroups WHERE is_active')).mappings()]
    accounts = [dict(r) for r in db.execute(text('SELECT id,account_number,account_type,normal_balance,is_active,is_posting FROM chart_of_accounts')).mappings()]
    return products, groups, subgroups, accounts


def apply_rows(db, source, rows, user=None):
    from app.models.product import Product
    from app.services.audit import record_audit
    from app.services.item_code import next_item_code
    created = []
    for row in rows:
        if row['seed_status'] != 'CREATE': continue
        profile = row['new_product']
        product = Product(code=next_item_code(db, profile['group_code'], profile['subgroup_code']), **profile)
        db.add(product)
        db.flush()
        record_audit(db, user, 'HOTEL_BUY_ITEM_CREATED', 'PRODUCT', f'Create Hotel BUY item {product.code}',
                     entity_id=product.id, after_data={**profile, 'code': product.code, 'id': product.id},
                     details={'module': 'Item Master', 'source_sha256': source['source_sha256'],
                              'source_sheet': source['sheet'], 'source_row': row['source_row'],
                              'legacy_code': row['legacy_code'], 'source_category': row['section_name'],
                              'source_purchase_reference': row['purchase'], 'source_expense_reference': row['expense'],
                              'stock_created': False, 'accounting_created': False, 'tax_review_required': True})
        created.append({'id': product.id, 'code': product.code, 'source_row': row['source_row']})
    return created


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--output', type=Path, default=Path('/tmp/hotel-item-seed-dry-run.json'))
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--actor-id', type=int)
    args = parser.parse_args()
    source = read_source(args.source)
    # Validate output location before any database mutation.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text('{}\n', encoding='utf-8')
    from sqlalchemy import text
    from app.core.database import SessionLocal
    from app.models.user import User
    from app.services.item_code import lock_item_creation
    with SessionLocal() as db:
        try:
            if not args.apply and db.get_bind().dialect.name == 'postgresql':
                db.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
            if args.apply:
                if db.get_bind().dialect.name == 'postgresql':
                    db.execute(text("SET LOCAL lock_timeout='5s'"))
                lock_item_creation(db)
                if db.get_bind().dialect.name == 'postgresql':
                    db.execute(text('LOCK TABLE products,item_groups,item_subgroups,chart_of_accounts IN SHARE ROW EXCLUSIVE MODE'))
            user = db.get(User, args.actor_id) if args.actor_id else None
            if args.actor_id and not user: raise ValueError('Audit actor does not exist')
            rows = seed_plan(source, *database_snapshot(db))
            created = apply_rows(db, source, rows, user) if args.apply else []
            summary = {'mode': 'APPLY' if args.apply else 'DRY_RUN',
                       'source_sha256': source['source_sha256'], 'catalog_type': 'HOTEL',
                       'source_items': len(rows), 'counts': dict(Counter(r['seed_status'] for r in rows)),
                       'create_by_subgroup': dict(Counter(f"{r['group']} / {r['subgroup']}" for r in rows if r['seed_status'] == 'CREATE')),
                       'review_reasons': dict(Counter(i for r in rows if r['seed_status'] == 'REVIEW' for i in set(r['issues']) - INFORMATIONAL)),
                       'created_items': len(created), 'full_seed_ready': not any(r['seed_status'] == 'REVIEW' for r in rows), 'price_policy': 'Editable legacy Purchase reference; Expense not imported',
                       'tax_policy': 'REVIEW_REQUIRED; no tax evidence supplied'}
            args.output.write_text(json.dumps({'summary': summary, 'items': rows, 'created': created}, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
            if args.apply: db.commit()
            else: db.rollback()
            print(json.dumps(summary, indent=2))
            print(f'Full report: {args.output}')
            print('COMMITTED Hotel Item Master and audit records only.' if args.apply else 'DRY RUN: no writes. Use --apply to create the classified subset.')
        except Exception:
            db.rollback()
            raise


if __name__ == '__main__': main()
