#!/usr/bin/env python3
"""Complete the user-confirmed Direct Use history of receiving 661.

Run repair_direct_use_receiving_history.py first. Dry-run is read-only.
This removes the remaining six false warehouse INs, expenses their value in
the original journal, and sets Direct Use with no warehouse. It never creates
an OUT or another journal. Product defaults, tax, invoice and AP stay intact.
"""
import argparse
from collections import Counter
from datetime import date
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from repair_direct_use_receiving_history import (
    ZERO, amount, signature, match_rows, receiving_signature, plan_stock,
)

ACTION = 'RECEIPT_DIRECT_USE_COMPLETED'
REMAINING = {6312, 6317, 6326, 6332, 6338, 6339}
DAY = date(2026, 1, 1)


def validate_remaining_stock(items, movements, inventory):
    """Only remove the six traced INs when no subsequent history exists."""
    if len(items) != 6 or {r['product_id'] for r in items} != REMAINING:
        raise ValueError('Remaining item evidence changed')
    if len(movements) != 6 or len(inventory) != 6:
        raise ValueError('Other stock history or inventory exists; inspection required')
    for item in items:
        pid = item['product_id']
        matches = [m for m in movements if m['product_id'] == pid]
        stocks = [s for s in inventory if s['product_id'] == pid]
        if len(matches) != 1 or len(stocks) != 1:
            raise ValueError(f'Item {pid} warehouse evidence is not unique')
        movement, stock = matches[0], stocks[0]
        inventory_account = 177 if pid == 6332 else 167
        # created_at records when a historical receipt was entered, not its
        # effective date. The receipt date and original posted journal/GL are
        # checked separately in main(). Legacy receipt INs may have no journal
        # FK; their receipt/item references still identify the source exactly.
        checks = {
            'movement_type': (movement['movement_type'], 'IN'),
            'reference_type': (movement['reference_type'], 'GOODS_RECEIPT'),
            'reference_id': (movement['reference_id'], 661),
            'goods_receipt_id': (movement['goods_receipt_id'], 661),
            'goods_receipt_item_id': (movement['goods_receipt_item_id'], item['receipt_item_id']),
            'movement.warehouse_id': (movement['warehouse_id'], 11),
            'inventory_account_id': (movement['inventory_account_id'], inventory_account),
            'movement.quantity': (amount(movement['quantity']), amount(item['quantity'])),
            'movement.unit_cost': (amount(movement['unit_cost']), amount(item['unit_cost'])),
            'inventory.warehouse_id': (stock['warehouse_id'], 11),
            'inventory.quantity': (amount(stock['quantity']), amount(item['quantity'])),
            'inventory.average_cost': (amount(stock['average_cost']), amount(item['unit_cost'])),
        }
        differences = {field: {'actual': str(actual), 'expected': str(expected)}
                       for field, (actual, expected) in checks.items() if actual != expected}
        if movement['journal_entry_id'] not in (None, 1332):
            differences['journal_entry_id'] = {
                'actual': str(movement['journal_entry_id']), 'expected': 'NULL or 1332'}
        if differences:
            raise ValueError(f'Item {pid} stock has changed; inspection required: '
                             + json.dumps(differences, sort_keys=True))


def target_signature(previous, items, products, accounts):
    plan = []
    for item in items:
        product = products[item['product_id']]
        account = accounts.get(product['purchase_account_id'])
        if (product['code'] != item['code'] or product['name'] != item['name']
                or product['item_type'] != 'BUY' or product['inventory_treatment'] != 'STOCK'
                or not account or not account['is_active'] or not account['is_posting']
                or account['account_type'] != 'EXPENSE' or account['normal_balance'] != 'DEBIT'):
            raise ValueError(f'Item {item["product_id"]} requires verified expense mapping')
        if account['id'] not in {37, 39}:
            raise ValueError('Expense mapping differs from traced food/beverage accounts')
        plan.append({'inventory_account_id':177 if item['product_id']==6332 else 167,
                     'expense_account_id':account['id'],
                     'value':amount(item['quantity']) * amount(item['unit_cost'])})
    result = receiving_signature(previous, plan)
    if any(accounts[a]['account_type'] == 'ASSET' for a, _, _ in result):
        raise ValueError('Inventory debit remains in Direct Use receiving')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--actor-id', type=int)
    args = parser.parse_args()
    from sqlalchemy import text
    from app.core.database import SessionLocal
    from app.services.fiscal_period_service import FiscalPeriodService
    manifest = json.loads(Path(__file__).with_name('item_stock_correction_20261005.json').read_text())
    evidence = json.loads(Path(__file__).with_name('receipt_661_direct_use_manifest.json').read_text())
    rules = {r['id']:r for r in json.loads(Path(__file__).with_name('item_classification_rules_20261005.json').read_text())}
    first_plan = plan_stock(manifest, manifest['pending_items'], manifest['inventory'],
                            manifest['movements'], manifest['receipt_items'], rules)
    for item in first_plan:
        item['expense_account_id'] = 37 if item['expense_code']=='500-100-100' else 39
    previous = [{'account_id':a,'debit':d,'credit':c}
                for a,d,c in receiving_signature(manifest['journal_lines'], first_plan).elements()]
    ids = [r['product_id'] for r in evidence]
    remaining = [r for r in evidence if r['product_id'] in REMAINING]
    if len(evidence) != 28 or len(set(ids)) != 28:
        raise ValueError('Pinned 28-item evidence changed')
    with SessionLocal() as db:
        try:
            if not args.apply:
                db.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
            db.execute(text("SET LOCAL lock_timeout='5s'"))
            db.execute(text("SET LOCAL statement_timeout='60s'"))
            if args.apply:
                db.execute(text('SELECT pg_advisory_xact_lock(484005,237)'))
                db.execute(text("""LOCK TABLE products, goods_receipts, goods_receipt_items,
                    inventory, stock_movements, journal_entries, journal_lines, general_ledger,
                    chart_of_accounts, fiscal_periods, audit_logs IN SHARE ROW EXCLUSIVE MODE"""))

            def rows(sql, params=None):
                return [dict(r) for r in db.execute(text(sql), params or {}).mappings()]

            receipt = rows('SELECT * FROM goods_receipts WHERE id=661')[0]
            if (receipt['receipt_number'] != 'GR-20260925-00007' or receipt['status'] != 'POSTED'
                    or receipt['received_at'].date() != DAY or receipt['supplier_id'] != 243
                    or amount(receipt['subtotal']) != amount('4025000')
                    or amount(receipt['total_amount']) != amount('4025000')
                    or amount(receipt['tax_amount']) != ZERO):
                raise ValueError('Receiving identity, date or totals changed')
            items = rows('SELECT * FROM goods_receipt_items WHERE goods_receipt_id=661')
            match_rows(items, [{**r,'id':r['receipt_item_id']} for r in evidence],
                       ('product_id','quantity','unit_cost','is_taxable','tax_rate','tax_amount'),
                       ('quantity','unit_cost','tax_rate','tax_amount'))
            journals = rows("SELECT * FROM journal_entries WHERE reference_type='GOODS_RECEIPT' AND reference_id=661")
            if (len(journals) != 1 or journals[0]['id'] != 1332
                    or journals[0]['status'] != 'POSTED' or journals[0]['posting_date'] != DAY
                    or journals[0]['journal_number'] != manifest['journal']['journal_number']
                    or journals[0]['document_number'] != receipt['receipt_number']):
                raise ValueError('Original receiving journal changed')
            lines = rows('SELECT * FROM journal_lines WHERE journal_entry_id=1332')
            ledger = rows("SELECT * FROM general_ledger WHERE reference_type='GOODS_RECEIPT' AND reference_id=661")
            if any(g['posting_date'] != DAY or g['reference_number'] != journals[0]['journal_number']
                   or g['document_number'] != receipt['receipt_number'] for g in ledger):
                raise ValueError('Source ledger date/link changed')
            movements = rows('SELECT * FROM stock_movements WHERE product_id=ANY(:ids) OR goods_receipt_id=661 OR journal_entry_id=1332', {'ids':ids})
            stock = rows('SELECT * FROM inventory WHERE product_id=ANY(:ids)', {'ids':ids})
            applied = rows("SELECT * FROM audit_logs WHERE entity_type='GOODS_RECEIPT' AND entity_id=661 AND action=:action", {'action':ACTION})
            if applied:
                saved = applied[0]['after_data']
                if isinstance(saved,str):
                    saved=json.loads(saved)
                expected=signature(saved['journal_lines'])
                if (receipt['destination_type'] != 'DIRECT_USE' or receipt['warehouse_id'] is not None
                        or movements or stock or signature(lines)!=expected or signature(ledger)!=expected):
                    raise ValueError('Previously completed Direct Use history has changed')
                print('ALREADY APPLIED: receiving 661 is Direct Use, no warehouse or stock movements; original journal/GL verified. No writes.')
                db.rollback()
                return
            if receipt['destination_type'] != 'WAREHOUSE' or receipt['warehouse_id'] != 11:
                raise ValueError('Receiving destination changed')
            if not rows("SELECT id FROM audit_logs WHERE entity_type='GOODS_RECEIPT' AND entity_id=661 AND action='DIRECT_USE_HISTORY_REPAIRED'"):
                raise ValueError('Run repair_direct_use_receiving_history.py first')
            if signature(lines)!=signature(previous) or signature(ledger)!=signature(previous):
                raise ValueError('Expected first 22-item repair is not present')
            validate_remaining_stock(remaining, movements, stock)
            products={p['id']:p for p in rows('SELECT * FROM products WHERE id=ANY(:ids)', {'ids':list(REMAINING)})}
            accounts={a['id']:a for a in rows('SELECT * FROM chart_of_accounts')}
            expected=target_signature(previous, remaining, products, accounts)
            FiscalPeriodService.validate_posting_date(db=db, posting_date=DAY)
            report={'mode':'APPLY' if args.apply else 'DRY_RUN','receipt':receipt['receipt_number'],
                    'destination':'DIRECT_USE','warehouse':None,'items':28,'remaining_false_in_to_remove':6,
                    'remaining_value_to_expense':'1360000.00',
                    'journal_lines':[{'account':accounts[a]['account_number'],'debit':str(d),'credit':str(c)}
                                     for a,d,c in expected.elements()]}
            print(json.dumps(report,indent=2))
            if not args.apply:
                db.rollback()
                print('DRY RUN: no writes. Use --apply to commit.')
                return
            before={'receipt':receipt,'journal_lines':lines,'general_ledger':ledger,
                    'false_in':movements,'inventory':stock}
            wanted={a:(d,c) for a,d,c in expected.elements()}
            if not set(wanted) <= {r['account_id'] for r in lines}:
                raise ValueError('Unexpected new account required')
            for table, records in [('journal_lines',lines),('general_ledger',ledger)]:
                for record in records:
                    if record['account_id'] not in wanted:
                        db.execute(text(f'DELETE FROM {table} WHERE id=:id'), {'id':record['id']})
                    else:
                        debit,credit=wanted[record['account_id']]
                        db.execute(text(f'UPDATE {table} SET debit=:debit,credit=:credit WHERE id=:id'),
                                   {'id':record['id'],'debit':debit,'credit':credit})
            db.execute(text('DELETE FROM stock_movements WHERE id=ANY(:ids)'), {'ids':[m['id'] for m in movements]})
            db.execute(text('DELETE FROM inventory WHERE id=ANY(:ids)'), {'ids':[s['id'] for s in stock]})
            db.execute(text("UPDATE goods_receipts SET destination_type='DIRECT_USE',warehouse_id=NULL,updated_at=now() WHERE id=661"))
            db.execute(text('UPDATE journal_entries SET updated_at=now() WHERE id=1332'))
            after_lines=rows('SELECT * FROM journal_lines WHERE journal_entry_id=1332')
            after_gl=rows("SELECT * FROM general_ledger WHERE reference_type='GOODS_RECEIPT' AND reference_id=661")
            if signature(after_lines)!=expected or signature(after_gl)!=expected:
                raise ValueError('Accounting verification failed')
            if rows('SELECT id FROM stock_movements WHERE product_id=ANY(:ids) OR goods_receipt_id=661', {'ids':ids}) or rows('SELECT id FROM inventory WHERE product_id=ANY(:ids)', {'ids':ids}):
                raise ValueError('False warehouse history remains')
            actor_name='EC2 operator'
            if args.actor_id:
                actor=rows('SELECT to_jsonb(u) AS actor FROM users u WHERE id=:id', {'id':args.actor_id})
                if not actor:
                    raise ValueError('Actor missing')
                actor_name=actor[0]['actor'].get('full_name') or actor_name
            db.execute(text("""INSERT INTO audit_logs
                (user_id,actor_name,entity_type,entity_id,action,summary,source,before_data,after_data,details)
                VALUES (:actor,:name,'GOODS_RECEIPT',661,:action,:summary,'EC2_SCRIPT',
                        CAST(:before AS json),CAST(:after AS json),CAST(:details AS json))"""),
                {'actor':args.actor_id,'name':actor_name,'action':ACTION,
                 'summary':'Complete actual Direct Use receiving history for all 28 items',
                 'before':json.dumps(before,default=str),
                 'after':json.dumps({'journal_lines':after_lines,'general_ledger':after_gl,
                                     'destination_type':'DIRECT_USE','warehouse_id':None},default=str),
                 'details':json.dumps(report)})
            db.commit()
            print('COMMITTED: receiving 661 is Direct Use; remaining six false INs removed; original journal 1332 expenses all Rp 4,025,000. Invoice, AP, tax, product defaults and opening balances unchanged.')
        except Exception:
            db.rollback()
            raise


if __name__=='__main__':
    main()
