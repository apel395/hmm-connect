#!/usr/bin/env python3
"""Restore actual direct-use history for the 22 prepared items from GR 661.

These items never entered a warehouse. Remove their false IN and synthetic OUT
rows and the ICR journal, then expense them in the original receiving journal.
Dry-run by default; apply is atomic and keeps account balances unchanged.
"""
from collections import Counter, defaultdict
from datetime import date
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from correct_item_classification import resolve_group, resolve_subgroup
from correct_prepared_item_stock import (
    MARKER, DOCUMENT, ZERO, amount, signature, match_rows, plan_stock, correction_signature,
)

AUDIT_ACTION = 'DIRECT_USE_HISTORY_REPAIRED'


def receiving_signature(source_lines, plan):
    """Move the original inventory debits to direct-use expense; keep AP."""
    debits, credits = defaultdict(lambda: ZERO), defaultdict(lambda: ZERO)
    for line in source_lines:
        debits[line['account_id']] += amount(line['debit'])
        credits[line['account_id']] += amount(line['credit'])
    for item in plan:
        debits[item['inventory_account_id']] -= item['value']
        debits[item['expense_account_id']] += item['value']
    if any(v < ZERO for v in debits.values()):
        raise ValueError('Direct-use amount exceeds original inventory debit')
    result = Counter((acct, debits[acct], credits[acct]) for acct in debits.keys() | credits.keys()
                     if debits[acct] or credits[acct])
    if sum(d * n for (_, d, _), n in result.items()) != sum(c * n for (_, _, c), n in result.items()):
        raise ValueError('Repaired receiving journal is unbalanced')
    return result


def balances(rows):
    result = defaultdict(lambda: ZERO)
    for row in rows:
        result[row['account_id']] += amount(row['debit']) - amount(row['credit'])
    return {k:v for k,v in result.items() if v}


def validate_outs(outs, plan, journal_id, effective_date):
    if len(outs) != 22 or {o['product_id'] for o in outs} != {p['product_id'] for p in plan}:
        raise ValueError('Synthetic OUT rows do not match the 22 traced items')
    for item in plan:
        out = next(o for o in outs if o['product_id'] == item['product_id'])
        if (out['movement_type'] != 'OUT' or out['reference_type'] != MARKER
                or out['reference_id'] != 661 or out['journal_entry_id'] != journal_id
                or out['goods_receipt_id'] != 661 or out['goods_receipt_item_id'] != item['receipt_item_id']
                or out['warehouse_id'] != 11 or out['inventory_account_id'] != item['inventory_account_id']
                or out['offset_account_id'] != item['expense_account_id']
                or amount(out['quantity']) != item['quantity'] or amount(out['unit_cost']) != item['unit_cost']
                or out['created_at'] != effective_date):
            raise ValueError(f'Synthetic OUT for item {item["product_id"]} changed; repair refused')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--actor-id', type=int)
    args = parser.parse_args()
    from sqlalchemy import text
    from app.core.database import SessionLocal
    from app.services.fiscal_period_service import FiscalPeriodService
    from app.services.general_ledger import GeneralLedgerService

    manifest = json.loads(Path(__file__).with_name('item_stock_correction_20261005.json').read_text())
    rules = {r['id']:r for r in json.loads(Path(__file__).with_name('item_classification_rules_20261005.json').read_text())}
    ids = [p['id'] for p in manifest['pending_items']]
    day = date.fromisoformat(manifest['journal']['posting_date'])
    plan = plan_stock(manifest, manifest['pending_items'], manifest['inventory'],
                      manifest['movements'], manifest['receipt_items'], rules)
    with SessionLocal() as db:
        try:
            if not args.apply:
                db.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
            db.execute(text("SET LOCAL lock_timeout='5s'"))
            db.execute(text("SET LOCAL statement_timeout='60s'"))
            if args.apply:
                db.execute(text('SELECT pg_advisory_xact_lock(484005,237)'))
                db.execute(text('''LOCK TABLE products, inventory, stock_movements, goods_receipts, goods_receipt_items,
                    journal_entries, journal_lines, general_ledger, item_groups, item_subgroups, fiscal_periods,
                    audit_logs IN SHARE ROW EXCLUSIVE MODE'''))

            def rows(sql, params=None):
                return [dict(r) for r in db.execute(text(sql), params or {}).mappings()]

            actor_name = 'EC2 operator'
            if args.actor_id:
                actors = rows('SELECT to_jsonb(u) AS actor FROM users u WHERE id=:id', {'id':args.actor_id})
                if not actors:
                    raise ValueError('Actor user missing')
                actor_name = actors[0]['actor'].get('full_name') or actors[0]['actor'].get('username') or actor_name
            accounts = {a['account_number']:a for a in rows('SELECT * FROM chart_of_accounts')}
            for item in plan:
                account = accounts.get(item['expense_code'])
                if not account or not account['is_active'] or not account['is_posting'] or account['account_type'] != 'EXPENSE' or account['normal_balance'] != 'DEBIT':
                    raise ValueError(f'Invalid expense account {item["expense_code"]}')
                item['expense_account_id'] = account['id']
            expected_source = receiving_signature(manifest['journal_lines'], plan)
            if balances(manifest['general_ledger'] + [
                {'account_id':a,'debit':d,'credit':c} for a,d,c in correction_signature(plan).elements()
            ]) != balances([{'account_id':a,'debit':d,'credit':c} for a,d,c in expected_source.elements()]):
                raise ValueError('Repair would change account balances')

            products = rows('SELECT * FROM products WHERE id=ANY(:ids)', {'ids':ids})
            if len(products) != 22:
                raise ValueError('Traced products missing')
            groups = rows('SELECT id,code,name,item_type,is_active FROM item_groups')
            subgroups = rows('SELECT id,code,name,group_id,is_active FROM item_subgroups')
            snapshots = rows("SELECT DISTINCT group_code,group_name,subgroup_code,subgroup_name FROM products WHERE item_type='BUY' AND is_active=true")
            for item in plan:
                p = next(p for p in products if p['id'] == item['product_id'])
                rule = rules[p['id']]
                group = resolve_group(groups, snapshots, rule['group'])
                subgroup = resolve_subgroup(subgroups, snapshots, group, rule['subgroups'])
                if (p['code'] != rule['code'] or p['name'] != rule['name'] or p['item_type'] != 'BUY'
                        or p['inventory_treatment'] != 'DIRECT_USE' or p['inventory_account_id'] is not None
                        or p['purchase_account_id'] != item['expense_account_id'] or p['cogs_account_id'] is not None
                        or p['asset_account_id'] is not None or p['group_code'] != group['code']
                        or p['subgroup_code'] != subgroup['code']):
                    raise ValueError(f'Direct-use item {p["id"]} changed; repair refused')
            receipt_items = rows('SELECT * FROM goods_receipt_items WHERE goods_receipt_id=661 AND product_id=ANY(:ids)', {'ids':ids})
            match_rows(receipt_items, manifest['receipt_items'],
                       ('product_id','goods_receipt_id','quantity','unit_cost','is_taxable','tax_rate','tax_amount'),
                       ('quantity','unit_cost','tax_rate','tax_amount'))
            receipts = rows('SELECT * FROM goods_receipts WHERE id=661')
            match_rows(receipts, [manifest['receipt']],
                       ('receipt_number','status','warehouse_id','destination_type','supplier_id',
                        'business_unit_id','location_id','department_id','subtotal','tax_amount','total_amount'),
                       ('subtotal','tax_amount','total_amount'))
            receipt = receipts[0]
            if receipt['received_at'].date() != day:
                raise ValueError('Original receiving date changed')
            journals = rows("SELECT * FROM journal_entries WHERE reference_type='GOODS_RECEIPT' AND reference_id=661")
            match_rows(journals, [manifest['journal']], ('journal_number','status','document_number','reference_type','reference_id'))
            if journals[0]['posting_date'] != day:
                raise ValueError('Original journal date changed')
            source_lines = rows('SELECT * FROM journal_lines WHERE journal_entry_id=1332')
            source_gl = rows("SELECT * FROM general_ledger WHERE reference_type='GOODS_RECEIPT' AND reference_id=661")
            correction = rows('SELECT * FROM journal_entries WHERE (reference_type=:ref AND reference_id=661) OR document_number=:doc', {'ref':MARKER,'doc':DOCUMENT})
            correction_gl = rows('''SELECT * FROM general_ledger WHERE (reference_type=:ref AND reference_id=661)
                OR document_number=:doc OR reference_number='ICR-202610-000001' ''', {'ref':MARKER,'doc':DOCUMENT})
            movements = rows('SELECT * FROM stock_movements WHERE product_id=ANY(:ids)', {'ids':ids})
            inventory = rows('SELECT * FROM inventory WHERE product_id=ANY(:ids)', {'ids':ids})
            audits = rows('SELECT id FROM audit_logs WHERE action=:action AND entity_type=\'GOODS_RECEIPT\' AND entity_id=661', {'action':AUDIT_ACTION})
            if audits:
                if correction or correction_gl or movements or inventory or signature(source_lines) != expected_source or signature(source_gl) != expected_source:
                    raise ValueError('Previously repaired history no longer matches expected state')
                if any(g['posting_date'] != day or g['reference_number'] != journals[0]['journal_number'] for g in source_gl):
                    raise ValueError('Repaired ledger date/link changed')
                print('ALREADY REPAIRED: 22 DIRECT_USE items have no warehouse rows or movements; original receiving journal/GL verified. No writes.')
                db.rollback()
                return

            if len(correction) != 1 or correction[0]['status'] != 'POSTED' or correction[0]['document_number'] != DOCUMENT or correction[0]['posting_date'] != day or correction[0]['reference_type'] != MARKER or correction[0]['reference_id'] != 661:
                raise ValueError('Expected posted ICR correction journal missing or changed')
            correction_journal = correction[0]
            correction_lines = rows('SELECT * FROM journal_lines WHERE journal_entry_id=:id', {'id':correction_journal['id']})
            if signature(correction_lines) != correction_signature(plan) or signature(correction_gl) != correction_signature(plan):
                raise ValueError('ICR journal and GL differ from traced correction')
            if any(g['posting_date'] != day or g['reference_number'] != correction_journal['journal_number'] or g['document_number'] != DOCUMENT or g['reference_type'] != MARKER or g['reference_id'] != 661 for g in correction_gl):
                raise ValueError('ICR ledger links changed')
            match_rows(source_lines, manifest['journal_lines'], ('account_id','debit','credit'), ('debit','credit'))
            match_rows(source_gl, manifest['general_ledger'], ('account_id','debit','credit'), ('debit','credit'))
            if any(g['posting_date'] != day or g['reference_number'] != journals[0]['journal_number'] for g in source_gl):
                raise ValueError('Original ledger date/link changed')
            original = [m for m in movements if m['reference_type'] == 'GOODS_RECEIPT']
            synthetic = [m for m in movements if m['reference_type'] == MARKER]
            if len(movements) != 44:
                raise ValueError('Other stock history exists; repair refused')
            match_rows(original, manifest['movements'],
                       ('product_id','warehouse_id','goods_receipt_id','goods_receipt_item_id','movement_type',
                        'reference_type','reference_id','quantity','unit_cost','inventory_account_id','offset_account_id','journal_entry_id'),
                       ('quantity','unit_cost'))
            validate_outs(synthetic, plan, correction_journal['id'], receipt['received_at'])
            match_rows(inventory, [{**s,'quantity':'0','average_cost':'0'} for s in manifest['inventory']],
                       ('product_id','warehouse_id','quantity','average_cost'), ('quantity','average_cost'))
            if rows('SELECT id FROM stock_movements WHERE journal_entry_id=:id AND NOT(product_id=ANY(:ids))', {'id':correction_journal['id'],'ids':ids}):
                raise ValueError('ICR journal has unrelated stock links')
            FiscalPeriodService.validate_posting_date(db=db, posting_date=day)
            report = {'mode':'APPLY' if args.apply else 'DRY_RUN', 'items':22,
                      'delete_false_in':22,'delete_synthetic_out':22,'delete_empty_inventory_rows':22,
                      'remove_journal':correction_journal['journal_number'],
                      'original_receiving_journal':journals[0]['journal_number'],
                      'receiving_lines':list(expected_source.elements()), 'account_balances_unchanged':True}
            print(json.dumps(report, indent=2, default=str))
            if not args.apply:
                db.rollback()
                print('DRY RUN: no writes. Use --apply to repair actual direct-use history.')
                return

            before = {'receipt':receipt,'source_journal':journals[0], 'source_lines':source_lines,'source_gl':source_gl,
                      'temporary_journal':correction_journal,'temporary_lines':correction_lines,'temporary_gl':correction_gl,
                      'false_movements':movements,'empty_inventory':inventory}
            # Both the warehouse IN and fabricated OUT are false history. Keep
            # their complete snapshots in audit instead of retaining fake events.
            db.execute(text('DELETE FROM stock_movements WHERE id=ANY(:ids)'), {'ids':[m['id'] for m in movements]})
            db.execute(text('DELETE FROM inventory WHERE id=ANY(:ids)'), {'ids':[s['id'] for s in inventory]})
            db.execute(text('DELETE FROM general_ledger WHERE id=ANY(:ids)'), {'ids':[g['id'] for g in correction_gl]})
            db.execute(text('DELETE FROM journal_lines WHERE journal_entry_id=:id'), {'id':correction_journal['id']})
            db.execute(text('DELETE FROM journal_entries WHERE id=:id'), {'id':correction_journal['id']})

            wanted = {a:(d,c) for a,d,c in expected_source.elements()}
            for line in source_lines:
                matching_gl = next(g for g in source_gl if g['account_id'] == line['account_id'])
                if line['account_id'] not in wanted:
                    db.execute(text('DELETE FROM journal_lines WHERE id=:id'), {'id':line['id']})
                    db.execute(text('DELETE FROM general_ledger WHERE id=:id'), {'id':matching_gl['id']})
                else:
                    debit, credit = wanted.pop(line['account_id'])
                    for table,row in [('journal_lines',line),('general_ledger',matching_gl)]:
                        db.execute(text(f'UPDATE {table} SET debit=:debit,credit=:credit'+(', updated_at=now()' if table=='general_ledger' else '')+' WHERE id=:id'),
                                   {'debit':debit,'credit':credit,'id':row['id']})
            next_line = max(line['line_number'] for line in source_lines) + 1
            for account,(debit,credit) in sorted(wanted.items()):
                description = f'Direct-use meals/drinks received via {receipt["receipt_number"]}; never entered warehouse'
                db.execute(text('''INSERT INTO journal_lines
                    (journal_entry_id,account_id,debit,credit,description,line_number,business_unit_id,location_id,department_id,supplier_id)
                    VALUES (1332,:account,:debit,:credit,:description,:line,2,6,1,243)'''),
                    {'account':account,'debit':debit,'credit':credit,'description':description,'line':next_line})
                GeneralLedgerService.post(db=db, account_id=account,debit=debit,credit=credit,
                    posting_date=day,journal_source='GOODS_RECEIPT',document_type='GOODS_RECEIPT',document_number=receipt['receipt_number'],
                    reference_type='GOODS_RECEIPT',reference_id=661,reference_number=journals[0]['journal_number'],
                    description=description,user_id=args.actor_id)
                next_line += 1
            db.execute(text('UPDATE journal_entries SET updated_at=now() WHERE id=1332'))
            repaired_lines = rows('SELECT * FROM journal_lines WHERE journal_entry_id=1332')
            repaired_gl = rows("SELECT * FROM general_ledger WHERE reference_type='GOODS_RECEIPT' AND reference_id=661")
            if signature(repaired_lines) != expected_source or signature(repaired_gl) != expected_source or balances(source_gl+correction_gl) != balances(repaired_gl):
                raise ValueError('Repaired accounting verification failed; rollback')
            if rows('SELECT id FROM stock_movements WHERE product_id=ANY(:ids)', {'ids':ids}) or rows('SELECT id FROM inventory WHERE product_id=ANY(:ids)', {'ids':ids}):
                raise ValueError('False warehouse history remains; rollback')
            db.execute(text('''INSERT INTO audit_logs
                (user_id,actor_name,entity_type,entity_id,action,summary,source,before_data,after_data,details)
                VALUES (:actor,:name,'GOODS_RECEIPT',661,:action,:summary,'EC2_SCRIPT',
                        CAST(:before AS json),CAST(:after AS json),CAST(:details AS json))'''),
                {'actor':args.actor_id,'name':actor_name,'action':AUDIT_ACTION,
                 'summary':'Restore actual direct-use history: 22 prepared items never entered warehouse',
                 'before':json.dumps(before, default=str),
                 'after':json.dumps({'journal_id':1332,'journal_lines':repaired_lines,'general_ledger':repaired_gl,
                                    'warehouse_movements':[],'inventory_rows':[]}, default=str),
                 'details':json.dumps({**report,'reason':'User confirmed these items never touched warehouse',
                                       'product_ids':ids,'original_receipt_and_supplier_liability_preserved':True}, default=str)})
            db.commit()
            print('COMMITTED: false IN/OUT and ICR journal removed; 22 DIRECT_USE items accounted as expense in original receiving journal 1332. Account balances, receipt totals, supplier invoices, AP, tax and opening balances preserved.')
        except Exception:
            db.rollback()
            raise


if __name__ == '__main__':
    main()
