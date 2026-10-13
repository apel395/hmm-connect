"""Prepare Hotel BUY item seed plans without writing to the database.

The local source is read from invlistofgoods.xls. Legacy codes are
classification references, not unique product identifiers. No --apply mode.
"""
import argparse
import csv
import gzip
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SOURCE = Path(__file__).with_name('invlistofgoods.xls')


def read_source(path):
    if path.suffix.lower() == '.gz':
        with gzip.open(path, 'rt', encoding='utf-8') as handle: return json.load(handle)
    try:
        import xlrd
    except ImportError as exc:
        raise SystemExit('Reading .xls requires xlrd: .venv/bin/python -m pip install xlrd==2.0.2') from exc
    if not path.exists(): raise SystemExit(f'Source file missing: {path}')
    with open('/dev/null', 'w') as log: book = xlrd.open_workbook(path, logfile=log)
    sheet = book.sheet_by_index(0)
    if sheet.ncols < 7: raise ValueError('Expected Code, Goods, Unit, Remark, Purchase and Expense columns')
    items, section = [], None
    for index in range(sheet.nrows):
        row = sheet.row_values(index)
        if row[1] and row[2] and not row[0]: section = (str(row[1]), str(row[2]))
        elif isinstance(row[0], (int, float)) and row[2]:
            if section is None: raise ValueError(f'Item at row {index+1} has no source category')
            items.append(dict(source_row=index+1, source_number=int(row[0]), section_code=section[0],
                              section_name=section[1], legacy_code=str(row[1]), name=str(row[2]),
                              unit=str(row[3]), remark=str(row[4]), purchase=float(row[5] or 0), expense=float(row[6] or 0)))
    if not items: raise ValueError('No source item rows found')
    return dict(source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), source_file=path.name, sheet=sheet.name, items=items)


def normalize(value):
    return re.sub(r'\s+', ' ', str(value or '').strip()).upper()


def proposal(row):
    name = normalize(row['name'])
    prefix = name.split('-', 1)[0].strip()
    section = row['section_code']
    # Operating equipment explicitly assigned to ASSET by the hotel owner.
    asset_coa = None
    if section in {'13', '14'} and prefix == 'LINEN' and not re.search(r'\b(?:ANAK REL|REL GORDEN)\b', name):
        asset_coa = '100-900-100'
    if section == '15' and not re.search(r'\b(?:PLASTIK|AKRILIK|MELAMIN|PISAU BLENDER|BLENDER GOBLET)\b', name):
        if re.search(r'\b(?:SENDOK|GARPU|SPOON|FORK|CUTLERY|CUTLERIES)\b', name): asset_coa = '100-900-102'
        elif re.search(r'\b(?:GELAS|GLASS|GOBLET|PITCHER|IRISH)\b', name): asset_coa = '100-900-103'
        elif re.search(r'\b(?:PIRING|BOWL|CHILI DISH|TEA CUP|SAUCER)\b', name): asset_coa = '100-900-101'
    if asset_coa:
        issues = []
        if not normalize(row['unit']): issues.append('UNIT_MISSING')
        elif normalize(row['unit']) in {'1','PPN'}: issues.append('UNIT_REVIEW')
        if row['purchase'] < 0: issues.append('NEGATIVE_PURCHASE_REFERENCE')
        if row['expense'] < 0: issues.append('NEGATIVE_LEGACY_EXPENSE_REFERENCE')
        return {'group': 'ASSET', 'subgroup': 'FURNITURE', 'inventory_treatment': 'FIXED_ASSET',
                'asset_coa': asset_coa, 'issues': issues}
    food = {'MEAT': 'MEAT', 'POU': 'POULTRY', 'FISH': 'FISH',
            'SEA': 'SEAFOOD', 'SEAFOOD': 'SEAFOOD', 'VEG': 'VEGETABLES',
            'FRU': 'FRUIT', 'HERBS': 'HERB', 'HERB': 'HERB',
            'GRO': 'GROCERIES', 'CAN': 'GROCERIES', 'FROZEN': 'GROCERIES',
            'DAIRY GOODS': 'GROCERIES', 'SAUCES': 'GROCERIES',
            'COFFEE': 'GROCERIES', 'TEA': 'GROCERIES'}
    # COFFEE also labels milk powder, chocolate sprinkles and jam in
    # this source. Keep food ingredients in FOOD; syrup is explicit.
    beverage = prefix == 'BEV' or section == '02' or bool(re.search(r'\b(?:SYRUP|SIRUP)\b', name))
    group = 'BEVERAGE' if beverage else 'FOOD' if section == '01' else 'MATERIAL'
    subgroup = food.get(prefix) if group == 'FOOD' else None
    if group == 'BEVERAGE':
        if 'SYRUP' in name or 'SIRUP' in name: subgroup = 'SYRUP'
        elif any(word in name for word in ('MINERAL', 'AQUA', 'AIR MINUM')): subgroup = 'MINERAL WATER'
        elif any(word in name for word in ('SPRITE', 'FANTA', 'COCA COLA', 'POCARI')): subgroup = 'SOFT DRINK'
    elif group == 'MATERIAL':
        subgroup = {'04': 'GUEST SUPPLIES', '05': 'STATIONARY',
                    '06': 'CLEANING SUPPLIES', '12': 'GASOLINE'}.get(section)
        if prefix in {'PRI', 'SIGN'}: subgroup = 'PRINTING'
    flags = []
    if not subgroup: flags.append('SUBGROUP_MAPPING_REQUIRED')
    if not row['unit']: flags.append('UNIT_MISSING')
    elif normalize(row['unit']) in {'1', 'PPN'}: flags.append('UNIT_REVIEW')
    if row['purchase'] < 0: flags.append('NEGATIVE_PURCHASE_REFERENCE')
    if row['expense'] < 0: flags.append('NEGATIVE_LEGACY_EXPENSE_REFERENCE')
    if section in {'09', '10', '11', '15'}:
        flags.append('CONSUMABLE_OR_EQUIPMENT_REVIEW')
    # Warehouse use and capitalization cannot be inferred from list headings.
    treatment = None
    if group == 'FOOD' and prefix in food and prefix != 'FROZEN': treatment = 'STOCK'
    if beverage and normalize(row['unit']) != 'PORSI': treatment = 'STOCK'
    if normalize(row['unit']) == 'PORSI':
        flags.append('BUY_SELL_AND_READY_MEAL_USAGE_REVIEW')
    if not treatment: flags.append('TREATMENT_REVIEW')
    return {'group': group, 'subgroup': subgroup,
            'inventory_treatment': treatment, 'issues': flags}


def build_plan(source, products=(), groups=(), subgroups=(), database_checked=False):
    names = Counter(normalize(row['name']) for row in source['items'])
    rows = []
    for source_row in source['items']:
        row = dict(source_row)
        row.update(proposal(row))
        if names[normalize(row['name'])] > 1: row['issues'].append('DUPLICATE_SOURCE_NAME')
        row.update(catalog_type='HOTEL', item_type='BUY', tax_policy='NO_TAX_IN_SOURCE',
                   suggested_cost=row['purchase'] if row['purchase'] >= 0 else None)
        hotel = [p for p in products if p['catalog_type'] == 'HOTEL' and p['item_type'] == 'BUY'
                 and normalize(p['name']) == normalize(row['name'])]
        catering = [p['id'] for p in products if p['catalog_type'] == 'CATERING'
                    and normalize(p['name']) == normalize(row['name'])]
        row['existing_hotel_ids'] = [p['id'] for p in hotel]
        row['catering_name_matches'] = catering
        row['action'] = ('EXISTING_HOTEL_ITEM' if len(hotel) == 1 else 'NEW_HOTEL_ITEM') if products else 'DATABASE_CHECK_REQUIRED'
        if len(hotel) > 1: row['issues'].append('MULTIPLE_HOTEL_MATCHES')
        if hotel and normalize(hotel[0]['uom']) != normalize(row['unit']): row['issues'].append('EXISTING_UNIT_DIFFERS')
        if groups or database_checked:
            matched = [g for g in groups if normalize(g['name']) == row['group']]
            if len(matched) != 1: row['issues'].append('GROUP_NOT_UNIQUE')
            else:
                row['group_id'] = matched[0]['id']
                matched_sub = [s for s in subgroups if s['group_id'] == matched[0]['id']
                               and normalize(s['name']) in ({'GROCERIES', 'GRESORIS'}
                                   if row['subgroup'] == 'GROCERIES' else {row['subgroup']})]
                if len(matched_sub) == 1: row['subgroup_id'] = matched_sub[0]['id']
                else: row['issues'].append('SUBGROUP_NOT_UNIQUE')
        rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--check-db', action='store_true')
    parser.add_argument('--output', type=Path, default=Path('/tmp/hotel-item-seed-plan.json'))
    args = parser.parse_args()
    source = read_source(args.source)
    products, groups, subgroups, accounts = [], [], [], []
    if args.check_db:
        from sqlalchemy import text
        from app.core.database import SessionLocal
        with SessionLocal() as db:
            if db.bind.dialect.name == 'postgresql': db.execute(text('SET TRANSACTION READ ONLY'))
            products = [dict(r) for r in db.execute(text('SELECT id,name,uom,catalog_type,item_type FROM products')).mappings()]
            groups = [dict(r) for r in db.execute(text("SELECT id,name,code FROM item_groups WHERE is_active AND item_type IN ('BUY','ITEM')")).mappings()]
            subgroups = [dict(r) for r in db.execute(text('SELECT id,name,code,group_id FROM item_subgroups WHERE is_active')).mappings()]
            accounts = [dict(r) for r in db.execute(text("SELECT id,account_number,account_name,account_type,normal_balance,is_posting FROM chart_of_accounts WHERE is_active AND (account_number LIKE '100-300%' OR account_number LIKE '100-600%' OR account_number LIKE '100-900%' OR account_type = 'EXPENSE') ORDER BY account_number")).mappings()]
            db.rollback()
    rows = build_plan(source, products, groups, subgroups, database_checked=args.check_db)
    if args.check_db and not products:
        for row in rows: row['action'] = 'NEW_HOTEL_ITEM'
    summary = {'mode': 'READ_ONLY_PREPARATION', 'source_sha256': source['source_sha256'],
               'source_file': source['source_file'], 'catalog_type': 'HOTEL', 'source_items': len(rows),
               'database_checked': args.check_db, 'seed_ready': False,
               'source_categories': dict(Counter(r['section_name'] for r in rows)),
               'proposed_groups': dict(Counter(r['group'] for r in rows)),
               'issues': dict(Counter(issue for r in rows for issue in r['issues'])),
               'actions': dict(Counter(r['action'] for r in rows)),
               'active_buy_groups': groups, 'active_subgroups': subgroups,
               'candidate_accounts': accounts,
               'reason': 'Preparation only. Confirm subgroup/treatment and price meaning before seeding; no stock or opening balances imported.'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({'summary': summary, 'items': rows}, indent=2), encoding='utf-8')
    with args.output.with_suffix('.csv').open('w', newline='', encoding='utf-8-sig') as handle:
        fields = ['source_row','source_number','section_name','legacy_code','name','unit',
                  'purchase','expense','catalog_type','group','subgroup','inventory_treatment','action','issues']
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction='ignore'); writer.writeheader()
        for row in rows: writer.writerow({**row, 'issues': '; '.join(row['issues'])})
    print(json.dumps(summary, indent=2))
    print(f'Full plan: {args.output}\nReview CSV: {args.output.with_suffix(".csv")}\nREAD ONLY: no database writes. No apply mode.')


if __name__ == '__main__': main()
