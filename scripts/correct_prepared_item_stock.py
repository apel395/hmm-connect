#!/usr/bin/env python3
"""Superseded OUT correction; evidence helpers retained for the history repair.

The user confirmed these items never entered a warehouse. The executable is
disabled: use repair_direct_use_receiving_history.py to fix the original source.
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
    raise SystemExit(
        'Superseded: these prepared items never entered a warehouse. '
        'Do not create synthetic OUT movements. Run '
        'scripts/repair_direct_use_receiving_history.py (dry run), then --apply.'
    )


if __name__ == '__main__':
    main()
