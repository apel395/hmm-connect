#!/usr/bin/env python3
"""Correct vetted Item Master classifications; dry-run by default.

Use the authoritative XLSX next to this script. Tax and posted documents are
never rewritten. Accounting mapping/treatment changes with stock history are
deferred for a separate stock and GL correction. --apply commits eligible rows.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from read_item_classification_source import inspect

FIELDS = ('group_code', 'group_name', 'subgroup_code', 'subgroup_name',
          'inventory_treatment', 'inventory_account_id', 'purchase_account_id',
          'asset_account_id', 'cogs_account_id', 'is_market_item')
REVIEW_SHA256 = '7adc409f1e9873f3758d4db4d5d22e8b047773f5d2e5d87132705d9c0ceeacc0'


def normalize(value):
    return str(value or '').strip().upper()


def validate_account(account, code, treatment):
    if not account or account['account_number'] != code:
        raise ValueError(f'COA {code} missing')
    if not account['is_active'] or not account['is_posting']:
        raise ValueError(f'COA {code} must be active and posting')
    kind = 'ASSET' if treatment == 'STOCK' else 'EXPENSE'
    if normalize(account['account_type']) != kind or normalize(account['normal_balance']) != 'DEBIT':
        raise ValueError(f'COA {code} must be a debit-balance {kind}')


def build_changes(product, rule, group, subgroup, account, history):
    if product['code'] != rule['code'] or product['name'] != rule['name']:
        raise ValueError('Product identity differs from vetted source')
    if not product['is_active'] or product['item_type'] != 'BUY':
        raise ValueError('Item must be active BUY')
    if product['inventory_treatment'] not in ('STOCK', rule['treatment']):
        raise ValueError('Treatment changed since review; re-inspect item')
    validate_account(account, rule['account'], rule['treatment'])
    changes = dict(zip(FIELDS[:4], (group['code'], group['name'], subgroup['code'], subgroup['name'])))
    changes['inventory_treatment'] = rule['treatment']
    changes['is_market_item'] = normalize(subgroup['name']) in ('FRUIT', 'VEGETABLES')
    if rule['treatment'] == 'STOCK':
        changes.update(inventory_account_id=account['id'], purchase_account_id=None, asset_account_id=None)
        # Receiving does not require an OUT account. Do not carry a food OUT
        # account into a different item family.
        changes['cogs_account_id'] = product['cogs_account_id'] if normalize(product['group_name']) == normalize(rule['group']) else None
    else:
        changes.update(inventory_account_id=None, purchase_account_id=account['id'], asset_account_id=None, cogs_account_id=None)
    for field, original in rule['expected'].items():
        if product[field] != original and product[field] != changes.get(field, original):
            raise ValueError(f'{field} changed since the source audit; re-inspect this item')
    changes = {k: v for k, v in changes.items() if product[k] != v}
    accounting_change = any(k in changes for k in ('inventory_treatment', 'inventory_account_id'))
    if accounting_change and (history['has_stock'] or history['has_movements'] or history['has_posted_receipt']):
        return {}, 'Posted stock/receiving must be corrected together with its inventory GL before changing treatment or inventory COA', changes
    return changes, None, changes


def catalog(conn, sql, params):
    return [dict(r) for r in conn.execute(sql, params).mappings()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file', type=Path, default=Path(__file__).with_name('item-classification-review-237.xlsx'))
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--actor-id', type=int, help='Optional real app user ID for audit attribution')
    args = parser.parse_args()
    from sqlalchemy import text
    from app.core.database import engine
    content = args.file.read_bytes()
    review = inspect(content, 'Classification review', 237)
    if review['sha256'] != REVIEW_SHA256:
        raise ValueError('Source workbook changed. Re-vet the correction rules before applying them.')
    source = {r['ID']: r for r in review['records']}
    rules = json.loads(Path(__file__).with_name('item_classification_rules_20261005.json').read_text())
    rule_hash = hashlib.sha256(json.dumps(rules, sort_keys=True).encode()).hexdigest()
    results = []
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            if not args.apply:
                conn.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
            conn.execute(text("SET LOCAL lock_timeout = '5s'"))
            conn.execute(text("SET LOCAL statement_timeout = '60s'"))
            if args.apply:
                conn.execute(text('SELECT pg_advisory_xact_lock(484005, 237)'))
                conn.execute(text('LOCK TABLE item_groups, item_subgroups IN SHARE ROW EXCLUSIVE MODE'))
                conn.execute(text('LOCK TABLE inventory, stock_movements, goods_receipts, goods_receipt_items IN SHARE MODE'))
            products = catalog(conn, text('SELECT * FROM products WHERE id = ANY(:ids) ORDER BY id' + (' FOR UPDATE' if args.apply else '')), {'ids': list(source)})
            by_id = {p['id']: p for p in products}
            if len(by_id) != 237 or any(by_id[i]['code'] != r['Code'] or by_id[i]['name'] != r['Item'] for i, r in source.items()):
                raise ValueError('Source IDs, codes or names differ from DB; no changes allowed')
            groups = catalog(conn, text("SELECT id, code, name, is_active FROM item_groups WHERE item_type='BUY'"), {})
            subgroups = catalog(conn, text('SELECT id, code, name, group_id, is_active FROM item_subgroups'), {})
            accounts = {r['account_number']: r for r in catalog(conn, text('SELECT id, account_number, account_type, normal_balance, is_active, is_posting FROM chart_of_accounts'), {})}
            if args.apply:
                required_audit = {'user_id','entity_type','entity_id','action','summary','before_data','after_data','details','actor_name','source'}
                cols = catalog(conn, text("SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='audit_logs'"), {})
                if not required_audit.issubset({r['column_name'] for r in cols}):
                    raise ValueError('Audit schema unavailable; correction refused')
            actor = None
            if args.actor_id:
                actor = conn.execute(text('SELECT to_jsonb(u) FROM users u WHERE id=:id'), {'id': args.actor_id}).scalar()
                if not actor:
                    raise ValueError('Actor user ID does not exist')
            for rule in rules:
                product = by_id.get(rule['id'])
                entry = {'id': rule['id'], 'code': rule['code'], 'name': rule['name']}
                try:
                    if not product or source[rule['id']]['Code'] != rule['code']:
                        raise ValueError('Vetted rule not present in source')
                    target_groups = [g for g in groups if normalize(g['name']) == rule['group']]
                    if len(target_groups) != 1 or not target_groups[0]['is_active']:
                        raise ValueError(f"Active BUY group {rule['group']} not uniquely configured")
                    group = target_groups[0]
                    candidates = [s for s in subgroups if s['group_id'] == group['id'] and normalize(s['name']) in rule['subgroups']]
                    active = [s for s in candidates if s['is_active']]
                    # Preferred names are explicit in the vetted rule, not fuzzy matches.
                    subgroup = next((s for label in rule['subgroups'] for s in active if normalize(s['name']) == label), None)
                    new_subgroup = False
                    if subgroup is None:
                        if candidates:
                            raise ValueError('Target subgroup exists but is inactive')
                        used = {s['code'] for s in subgroups}
                        n = 1
                        while f"{group['code']}-{n}" in used:
                            n += 1
                        subgroup = {'id': None, 'code': f"{group['code']}-{n}", 'name': rule['subgroups'][0], 'group_id': group['id'], 'is_active': True}
                        if len(subgroup['code']) > 10:
                            raise ValueError('Subgroup code exceeds schema length')
                        new_subgroup = True
                    history = dict(conn.execute(text('''
                        SELECT
                          EXISTS(SELECT 1 FROM inventory WHERE product_id=:id AND quantity <> 0) AS has_stock,
                          EXISTS(SELECT 1 FROM stock_movements WHERE product_id=:id) AS has_movements,
                          EXISTS(SELECT 1 FROM goods_receipt_items i JOIN goods_receipts r ON r.id=i.goods_receipt_id
                                 WHERE i.product_id=:id AND r.status='POSTED') AS has_posted_receipt
                    '''), {'id': rule['id']}).mappings().one())
                    changes, blocked, proposed = build_changes(product, rule, group, subgroup, accounts.get(rule['account']), history)
                    entry.update(proposed=proposed, history=history)
                    if blocked:
                        entry.update(status='DEFERRED_POSTED_STOCK', reason=blocked)
                        entry['stock'] = catalog(conn, text('SELECT warehouse_id, quantity, average_cost FROM inventory WHERE product_id=:id ORDER BY warehouse_id'), {'id':rule['id']})
                        entry['receipts'] = catalog(conn, text('''
                            SELECT r.id, r.receipt_number, r.status, r.received_at, r.destination_type,
                                   i.id AS receipt_item_id, i.quantity, i.unit_cost,
                                   (SELECT jsonb_agg(jsonb_build_object('id', j.id, 'number',j.journal_number,'status',j.status))
                                    FROM journal_entries j WHERE j.reference_type='GOODS_RECEIPT' AND j.reference_id=r.id) AS journals
                            FROM goods_receipt_items i JOIN goods_receipts r ON r.id=i.goods_receipt_id
                            WHERE i.product_id=:id ORDER BY r.id, i.id
                        '''), {'id':rule['id']})
                    elif not changes:
                        entry['status'] = 'UNCHANGED'
                    else:
                        entry.update(status='APPLIED' if args.apply else 'PLANNED', changes=changes)
                        if new_subgroup:
                            entry['create_subgroup'] = {k: subgroup[k] for k in ('code','name','group_id')}
                        if args.apply:
                            if new_subgroup:
                                subgroup['id'] = conn.execute(text('INSERT INTO item_subgroups (code,name,group_id,is_active) VALUES (:code,:name,:group_id,true) RETURNING id'), subgroup).scalar_one()
                            assignment = ', '.join(f'{k}=:{k}' for k in changes)
                            conn.execute(text('UPDATE products SET '+assignment+', updated_at=now() WHERE id=:product_id'), {**changes, 'product_id': rule['id']})
                            before = {k: product[k] for k in FIELDS}
                            after = {**before, **changes}
                            conn.execute(text('''
                                INSERT INTO audit_logs
                                  (user_id,actor_name,entity_type,entity_id,action,summary,source,before_data,after_data,details)
                                VALUES (:user_id,:actor_name,'PRODUCT',:id,'ITEM_CLASSIFICATION_CORRECTED',:summary,'EC2_SCRIPT',
                                        CAST(:before AS json),CAST(:after AS json),CAST(:details AS json))
                            '''), {'user_id': args.actor_id, 'actor_name': (actor or {}).get('full_name') or (actor or {}).get('username') or 'EC2 operator', 'id': rule['id'], 'summary': f"Correct classification for {rule['code']}", 'before': json.dumps(before, default=str), 'after': json.dumps(after, default=str), 'details': json.dumps({'module':'Item Master', 'source_sha256':review['sha256'], 'rules_sha256':rule_hash, 'reason':rule['reason'], 'created_subgroup':entry.get('create_subgroup')})})
                        if new_subgroup:
                            subgroups.append(subgroup)
                except ValueError as exc:
                    entry.update(status='REVIEW_REQUIRED', reason=str(exc))
                results.append(entry)
            summary = {s: sum(r['status']==s for r in results) for s in sorted({r['status'] for r in results})}
            print(json.dumps({'mode':'APPLY' if args.apply else 'DRY_RUN', 'source_sha256':review['sha256'], 'rules_sha256':rule_hash, 'source_items':237, 'vetted_rules':len(rules), 'other_items':237-len(rules), 'summary':summary, 'results':results}, indent=2, default=str, ensure_ascii=False))
            if args.apply:
                transaction.commit()
                print('COMMITTED eligible Item Master corrections and audit records. Tax, stock and journals unchanged.')
            else:
                transaction.rollback()
                print('DRY RUN: no writes. Use --apply for eligible rows; deferred rows require stock/GL correction.')
        except Exception:
            transaction.rollback()
            raise


if __name__ == '__main__':
    main()
