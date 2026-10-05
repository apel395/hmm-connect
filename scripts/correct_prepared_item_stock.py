#!/usr/bin/env python3
"""Correct the 22 traced prepared items from GR 661, atomically; dry-run by default.

Record historical OUT movements and an expense/inventory journal, then switch
the vetted BUY items to DIRECT_USE. Original receiving, invoices, AP, tax and
opening balances are preserved. Refuse changed stock or accounting evidence.
"""
import argparse
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from correct_item_classification import FIELDS, build_changes, resolve_group, resolve_subgroup

MARKER = 'STOCK_CLASSIFICATION'
DOCUMENT = 'ICR-GR661-20261005'
ZERO = Decimal('0')
MONEY = Decimal('.01')


def amount(value):
    return Decimal(str(value))


def signature(rows):
    return Counter((r['account_id'], amount(r['debit']), amount(r['credit'])) for r in rows)


def match_rows(actual, expected, fields, numeric=()):
    if len(actual) != len(expected) or {r['id'] for r in actual} != {r['id'] for r in expected}:
        raise ValueError('Traced row identities changed; re-inspect before correction')
    expected = {r['id']: r for r in expected}
    for row in actual:
        old = expected[row['id']]
        for field in fields:
            left, right = row[field], old[field]
            if field in numeric:
                left, right = amount(left), amount(right)
            if left != right:
                raise ValueError(f'Row {row["id"]}: {field} changed; correction refused')


def plan_stock(manifest, products, inventory, movements, receipt_items, rules):
    match_rows(products, manifest['pending_items'],
               ('id','code','name','inventory_treatment','inventory_account_id','purchase_account_id'))
    match_rows(inventory, manifest['inventory'],
               ('product_id','warehouse_id','quantity','average_cost'), ('quantity','average_cost'))
    match_rows(movements, manifest['movements'],
               ('product_id','warehouse_id','goods_receipt_id','goods_receipt_item_id',
                'movement_type','reference_type','reference_id','quantity','unit_cost',
                'inventory_account_id','offset_account_id','journal_entry_id',
                'business_unit_id','location_id','department_id'), ('quantity','unit_cost'))
    match_rows(receipt_items, manifest['receipt_items'],
               ('product_id','goods_receipt_id','quantity','unit_cost','is_taxable','tax_rate','tax_amount'),
               ('quantity','unit_cost','tax_rate','tax_amount'))
    stocks = {r['product_id']: r for r in inventory}
    lines = {r['id']: r for r in receipt_items}
    if len(stocks) != 22 or len(movements) != 22:
        raise ValueError('Expected exactly one stock row and receiving IN per each of 22 items')
    result = []
    for movement in movements:
        pid = movement['product_id']
        rule = rules[pid]
        if rule['treatment'] != 'DIRECT_USE':
            raise ValueError('Only vetted DIRECT_USE rules are eligible')
        stock = stocks[pid]
        receipt_item = lines[movement['goods_receipt_item_id']]
        quantity, cost = amount(movement['quantity']), amount(movement['unit_cost'])
        if (movement['movement_type'] != 'IN' or movement['reference_type'] != 'GOODS_RECEIPT'
                or movement['reference_id'] != 661 or movement['goods_receipt_id'] != 661
                or movement['warehouse_id'] != 11 or quantity <= 0 or cost <= 0
                or amount(stock['quantity']) != quantity or amount(stock['average_cost']) != cost
                or amount(receipt_item['quantity']) != quantity or amount(receipt_item['unit_cost']) != cost):
            raise ValueError(f'Stock does not exactly match the original receiving for item {pid}')
        result.append({'product_id': pid, 'inventory_id': stock['id'], 'original_movement_id': movement['id'],
                       'receipt_item_id': receipt_item['id'], 'quantity': quantity, 'unit_cost': cost,
                       'inventory_account_id': movement['inventory_account_id'],
                       'expense_code': rule['account'], 'value': (quantity * cost).quantize(MONEY)})
    if sum((r['value'] for r in result), ZERO) != Decimal('2665000.00'):
        raise ValueError('Correction total differs from traced Rp 2,665,000')
    return result


def correction_signature(plan):
    totals = defaultdict(lambda: ZERO)
    for item in plan:
        totals[(item['expense_account_id'], 'DEBIT')] += item['value']
        totals[(item['inventory_account_id'], 'CREDIT')] += item['value']
    return Counter((account, value if side == 'DEBIT' else ZERO,
                    value if side == 'CREDIT' else ZERO) for (account, side), value in totals.items())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--actor-id', type=int, help='Optional app user for audit attribution')
    args = parser.parse_args()
    from sqlalchemy import text
    from app.core.database import SessionLocal
    from app.services.document_number import next_document_number
    from app.services.fiscal_period_service import FiscalPeriodService
    from app.services.general_ledger import GeneralLedgerService

    manifest = json.loads(Path(__file__).with_name('item_stock_correction_20261005.json').read_text())
    all_rules = json.loads(Path(__file__).with_name('item_classification_rules_20261005.json').read_text())
    rules = {r['id']: r for r in all_rules}
    ids = [r['id'] for r in manifest['pending_items']]
    posting_date = date.fromisoformat(manifest['journal']['posting_date'])
    with SessionLocal() as db:
        try:
            if not args.apply:
                db.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
            db.execute(text("SET LOCAL lock_timeout = '5s'"))
            db.execute(text("SET LOCAL statement_timeout = '60s'"))
            if args.apply:
                db.execute(text('SELECT pg_advisory_xact_lock(484005,237)'))
                db.execute(text('''LOCK TABLE products, inventory, stock_movements, goods_receipts,
                    goods_receipt_items, journal_entries, journal_lines, general_ledger,
                    item_groups, item_subgroups, fiscal_periods IN SHARE ROW EXCLUSIVE MODE'''))

            def rows(sql, params=None):
                return [dict(r) for r in db.execute(text(sql), params or {}).mappings()]

            def audit(entity, entity_id, before, after, details):
                db.execute(text('''INSERT INTO audit_logs
                    (user_id,actor_name,entity_type,entity_id,action,summary,source,before_data,after_data,details)
                    VALUES (:actor,:actor_name,:entity,:id,'PREPARED_ITEM_STOCK_CORRECTED',
                            :summary,'EC2_SCRIPT',CAST(:before AS json),CAST(:after AS json),CAST(:details AS json))'''),
                    {'actor': args.actor_id, 'actor_name': actor_name, 'entity': entity, 'id': entity_id,
                     'summary': f'Prepared item correction for GR 661 ({DOCUMENT})',
                     'before': json.dumps(before, default=str), 'after': json.dumps(after, default=str),
                     'details': json.dumps(details, default=str)})

            actor_name = 'EC2 operator'
            if args.actor_id:
                actors = rows('SELECT to_jsonb(u) AS actor FROM users u WHERE id=:id', {'id':args.actor_id})
                if not actors:
                    raise ValueError('Actor user does not exist')
                actor_name = actors[0]['actor'].get('full_name') or actors[0]['actor'].get('username') or actor_name
            products = rows('SELECT * FROM products WHERE id=ANY(:ids) ORDER BY id', {'ids':ids})
            inventory = rows('SELECT * FROM inventory WHERE product_id=ANY(:ids)', {'ids':ids})
            movements = rows('SELECT * FROM stock_movements WHERE product_id=ANY(:ids)', {'ids':ids})
            receipt_items = rows('SELECT * FROM goods_receipt_items WHERE goods_receipt_id=661 AND product_id=ANY(:ids)', {'ids':ids})
            receipts = rows('SELECT * FROM goods_receipts WHERE id=661')
            if len(receipts) != 1:
                raise ValueError('Receipt 661 missing')
            receipt = receipts[0]
            match_rows([receipt], [manifest['receipt']],
                       ('receipt_number','status','destination_type','warehouse_id','supplier_id',
                        'business_unit_id','location_id','department_id','subtotal','tax_amount','total_amount'),
                       ('subtotal','tax_amount','total_amount'))
            if receipt['received_at'].date() != posting_date:
                raise ValueError('Receipt effective date changed')
            journals = rows("SELECT * FROM journal_entries WHERE reference_type='GOODS_RECEIPT' AND reference_id=661")
            match_rows(journals, [manifest['journal']], ('journal_number','status','reference_type','reference_id','document_number'))
            if journals[0]['posting_date'] != posting_date:
                raise ValueError('Original journal date changed')
            source_lines = rows('SELECT * FROM journal_lines WHERE journal_entry_id=1332')
            source_gl = rows("SELECT * FROM general_ledger WHERE reference_type='GOODS_RECEIPT' AND reference_id=661")
            for actual, expected in ((source_lines, manifest['journal_lines']), (source_gl, manifest['general_ledger'])):
                match_rows(actual, expected, ('account_id','debit','credit'), ('debit','credit'))
            if signature(source_lines) != signature(source_gl) or any(r['posting_date'] != posting_date for r in source_gl):
                raise ValueError('Original journal and GL differ')
            accounts = {r['account_number']: r for r in rows('SELECT * FROM chart_of_accounts')}
            groups = rows('SELECT id,code,name,item_type,is_active FROM item_groups')
            subgroups = rows('SELECT id,code,name,group_id,is_active FROM item_subgroups')
            snapshots = rows("SELECT DISTINCT group_code,group_name,subgroup_code,subgroup_name FROM products WHERE item_type='BUY' AND is_active=true")
            # Construct the expected correction independently for completion checks.
            plan = plan_stock(manifest, manifest['pending_items'], manifest['inventory'],
                              manifest['movements'], manifest['receipt_items'], rules)
            for item in plan:
                account = accounts.get(item['expense_code'])
                if not account or not account['is_active'] or not account['is_posting'] or account['account_type'] != 'EXPENSE' or account['normal_balance'] != 'DEBIT':
                    raise ValueError(f'Invalid expense COA {item["expense_code"]}')
                item['expense_account_id'] = account['id']
                inv = next((a for a in accounts.values() if a['id'] == item['inventory_account_id']), None)
                if not inv or not inv['is_active'] or not inv['is_posting'] or inv['account_type'] != 'ASSET' or inv['normal_balance'] != 'DEBIT':
                    raise ValueError('Invalid source inventory COA')
            correction_journals = rows('SELECT * FROM journal_entries WHERE reference_type=:ref AND reference_id=661', {'ref':MARKER})
            correction_gl = rows('SELECT * FROM general_ledger WHERE reference_type=:ref AND reference_id=661', {'ref':MARKER})
            correction_movements = [m for m in movements if m['reference_type'] == MARKER]
            if correction_journals:
                if len(correction_journals) != 1 or correction_journals[0]['status'] != 'POSTED' or correction_journals[0]['document_number'] != DOCUMENT or correction_journals[0]['posting_date'] != posting_date:
                    raise ValueError('Existing correction journal changed; manual review required')
                correction = correction_journals[0]
                current_lines = rows('SELECT * FROM journal_lines WHERE journal_entry_id=:id', {'id':correction['id']})
                if signature(current_lines) != correction_signature(plan) or signature(correction_gl) != correction_signature(plan):
                    raise ValueError('Existing correction accounting incomplete')
                if any(r['posting_date'] != posting_date or r['reference_number'] != correction['journal_number'] or r['document_number'] != DOCUMENT for r in correction_gl):
                    raise ValueError('Existing correction GL dates or document links differ')
                if len(correction_movements) != 22 or len(movements) != 44 or len(products) != 22 or len(inventory) != 22:
                    raise ValueError('Existing correction stock incomplete')
                match_rows([m for m in movements if m['reference_type'] != MARKER], manifest['movements'],
                           ('product_id','quantity','unit_cost','inventory_account_id'), ('quantity','unit_cost'))
                for item in plan:
                    outs = [m for m in correction_movements if m['product_id'] == item['product_id']]
                    stocks = [s for s in inventory if s['product_id'] == item['product_id']]
                    p = next(p for p in products if p['id'] == item['product_id'])
                    if len(outs) != 1 or len(stocks) != 1:
                        raise ValueError('Existing correction stock identities differ')
                    out, stock = outs[0], stocks[0]
                    rule = rules[p['id']]
                    group = resolve_group(groups, snapshots, rule['group'])
                    subgroup = resolve_subgroup(subgroups, snapshots, group, rule['subgroups'])
                    if (out['movement_type'] != 'OUT' or out['journal_entry_id'] != correction['id']
                            or out['reference_id'] != 661 or out['warehouse_id'] != 11
                            or out['inventory_account_id'] != item['inventory_account_id']
                            or out['offset_account_id'] != item['expense_account_id']
                            or amount(out['quantity']) != item['quantity'] or amount(out['unit_cost']) != item['unit_cost']
                            or out['created_at'] != receipt['received_at'] or amount(stock['quantity']) != ZERO
                            or amount(stock['average_cost']) != ZERO or stock['warehouse_id'] != 11
                            or p['code'] != rule['code'] or p['name'] != rule['name'] or p['item_type'] != 'BUY'
                            or p['group_code'] != group['code'] or p['subgroup_code'] != subgroup['code']
                            or p['inventory_treatment'] != 'DIRECT_USE' or p['inventory_account_id'] is not None
                            or p['purchase_account_id'] != item['expense_account_id']
                            or p['cogs_account_id'] is not None or p['asset_account_id'] is not None):
                        raise ValueError('Existing correction differs from expected completed state')
                print('ALREADY APPLIED: 22 items, OUT movements and journal/GL verified. No writes.')
                db.rollback()
                return
            if correction_gl or correction_movements or rows('SELECT id FROM journal_entries WHERE document_number=:doc', {'doc':DOCUMENT}):
                raise ValueError('Partial or conflicting correction marker exists; correction refused')
            plan_stock(manifest, products, inventory, movements, receipt_items, rules)
            by_id = {p['id']: p for p in products}
            for item in plan:
                product, rule = by_id[item['product_id']], rules[item['product_id']]
                group = resolve_group(groups, snapshots, rule['group'])
                subgroup = resolve_subgroup(subgroups, snapshots, group, rule['subgroups'])
                if group.get('_new') or subgroup['id'] is None:
                    raise ValueError('Run Item Master catalog corrections first')
                item['changes'], _, _ = build_changes(product, rule, group, subgroup, accounts[rule['account']],
                    {'has_stock':False,'has_movements':False,'has_posted_receipt':False})
            # The effective date stays January 1, so historical stock/GL agree.
            # Never reopen a period or override the app's backdate policy.
            FiscalPeriodService.validate_posting_date(db=db, posting_date=posting_date)
            print(json.dumps({'mode':'APPLY' if args.apply else 'DRY_RUN', 'source_receipt':661,
                              'source_journal':1332, 'posting_date':posting_date, 'total':'2665000.00',
                              'stock_out_rows':len(plan), 'journal_lines':list(correction_signature(plan).elements()),
                              'items':plan}, indent=2, default=str))
            if not args.apply:
                db.rollback()
                print('DRY RUN: no changes. Use --apply to commit all 22 stock and accounting corrections together.')
                return
            journal_number = next_document_number(db, 'ICR', digits=6)
            journal_id = db.execute(text('''INSERT INTO journal_entries
                (journal_number,posting_date,status,document_type,document_number,reference_type,reference_id,
                 description,created_by_id,posted_by_id,posted_at,source_type,fiscal_year,fiscal_period,
                 business_unit_id,location_id,department_id)
                VALUES (:number,:day,'POSTED','STOCK_CLASSIFICATION',:doc,:ref,661,:description,
                        :actor,:actor,now(),'CORRECTION',2026,1,2,6,1) RETURNING id'''),
                {'number':journal_number,'day':posting_date,'doc':DOCUMENT,'ref':MARKER,'actor':args.actor_id,
                 'description':'Correct prepared meals/drinks from GR 661 to direct-use expense; original receipt retained'}).scalar_one()
            for n, (account_id, debit, credit) in enumerate(correction_signature(plan).elements(), 1):
                description = f'Prepared item stock correction for {receipt["receipt_number"]}'
                db.execute(text('''INSERT INTO journal_lines
                    (journal_entry_id,account_id,debit,credit,description,line_number,business_unit_id,location_id,department_id,supplier_id)
                    VALUES (:journal,:account,:debit,:credit,:description,:line,2,6,1,243)'''),
                    {'journal':journal_id,'account':account_id,'debit':debit,'credit':credit,'description':description,'line':n})
                GeneralLedgerService.post(db=db, account_id=account_id,debit=debit,credit=credit,
                    posting_date=posting_date,journal_source=MARKER,document_type=MARKER,document_number=DOCUMENT,
                    reference_type=MARKER,reference_id=661,reference_number=journal_number,
                    description=description,user_id=args.actor_id)
            for item in plan:
                movement_id = db.execute(text('''INSERT INTO stock_movements
                    (product_id,warehouse_id,goods_receipt_id,goods_receipt_item_id,movement_type,quantity,unit_cost,
                     reference_type,reference_id,notes,created_at,updated_at,business_unit_id,location_id,department_id,
                     inventory_account_id,offset_account_id,journal_entry_id)
                    VALUES (:product_id,11,661,:receipt_item_id,'OUT',:quantity,:unit_cost,:ref,661,:notes,:effective,now(),
                            2,6,1,:inventory_account_id,:expense_account_id,:journal) RETURNING id'''),
                    {**item,'ref':MARKER,'notes':f'Historical direct-use classification correction ({DOCUMENT}); original IN retained',
                     'effective':receipt['received_at'],'journal':journal_id}).scalar_one()
                db.execute(text('UPDATE inventory SET quantity=0, average_cost=0 WHERE id=:id'), {'id':item['inventory_id']})
                changes = item['changes']
                db.execute(text('UPDATE products SET '+', '.join(f'{k}=:{k}' for k in changes)+', updated_at=now() WHERE id=:id'),
                           {**changes,'id':item['product_id']})
                before = {k: by_id[item['product_id']][k] for k in FIELDS}
                audit('PRODUCT',item['product_id'],before,{**before,**changes},
                      {**item,'correction_journal_id':journal_id,'out_movement_id':movement_id,'source_receipt':661})
            new_lines = rows('SELECT * FROM journal_lines WHERE journal_entry_id=:id', {'id':journal_id})
            new_gl = rows('SELECT * FROM general_ledger WHERE reference_type=:ref AND reference_id=661', {'ref':MARKER})
            if signature(new_lines) != correction_signature(plan) or signature(new_gl) != correction_signature(plan):
                raise ValueError('Correction journal/GL verification failed; rollback')
            remaining_stock = rows('SELECT * FROM inventory WHERE product_id=ANY(:ids)', {'ids':ids})
            net_movements = rows('''SELECT product_id, warehouse_id,
                sum(CASE WHEN movement_type='OUT' THEN -quantity ELSE quantity END) AS net_qty,
                sum(CASE WHEN movement_type='OUT' THEN -quantity ELSE quantity END * unit_cost) AS net_value
                FROM stock_movements WHERE product_id=ANY(:ids) GROUP BY product_id,warehouse_id''', {'ids':ids})
            if len(remaining_stock) != 22 or len(net_movements) != 22 or any(amount(s['quantity']) != ZERO or amount(s['average_cost']) != ZERO for s in remaining_stock) or any(amount(m['net_qty']) != ZERO or amount(m['net_value']) != ZERO for m in net_movements):
                raise ValueError('Stock quantity/value verification failed; rollback')
            audit('JOURNAL_ENTRY',journal_id,None,{'journal_number':journal_number,'total':'2665000.00'},
                  {'original_journal_id':1332,'source_receipt':661,'stock_out_rows':22,'effective_date':posting_date})
            db.commit()
            print(f'COMMITTED: 22 items changed to DIRECT_USE, 22 historical OUT movements, journal {journal_number}, total Rp 2,665,000. Original receipt, invoice, AP, tax and opening balances preserved.')
        except Exception:
            db.rollback()
            raise


if __name__ == '__main__':
    main()
