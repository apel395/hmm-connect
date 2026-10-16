"""Read-only evidence for correcting Market List items incorrectly stocked."""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='/tmp/ml-stock-review.json')
    args=parser.parse_args()
    from sqlalchemy import text
    from app.core.database import SessionLocal
    from app.models.purchasing_item_policy import MARKET_SUBGROUPS
    with SessionLocal() as db:
        db.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        db.execute(text("SET LOCAL statement_timeout='60s'"))
        def rows(sql,params=None):
            return [dict(r) for r in db.execute(text(sql),params or {}).mappings()]
        products=rows('''SELECT p.*, a.account_number AS inventory_coa,
            e.account_number AS expense_coa FROM products p
            LEFT JOIN chart_of_accounts a ON a.id=p.inventory_account_id
            LEFT JOIN chart_of_accounts e ON e.id=p.purchase_account_id
            WHERE p.item_type='BUY' AND upper(trim(p.subgroup_name))=ANY(:families)
            AND (upper(trim(p.subgroup_name))<>'MEAT' OR p.is_market_item=true)
            ORDER BY p.catalog_type,p.code''',{'families':sorted(MARKET_SUBGROUPS)})
        ids=[p['id'] for p in products]
        inventory=rows('SELECT * FROM inventory WHERE product_id=ANY(:ids) ORDER BY product_id,warehouse_id',{'ids':ids}) if ids else []
        movements=rows('SELECT * FROM stock_movements WHERE product_id=ANY(:ids) ORDER BY product_id,id',{'ids':ids}) if ids else []
        items=rows('SELECT * FROM goods_receipt_items WHERE product_id=ANY(:ids) ORDER BY goods_receipt_id,id',{'ids':ids}) if ids else []
        receipt_ids=sorted({i['goods_receipt_id'] for i in items}|{m['goods_receipt_id'] for m in movements if m['goods_receipt_id']})
        receipts=rows('SELECT * FROM goods_receipts WHERE id=ANY(:ids) ORDER BY id',{'ids':receipt_ids}) if receipt_ids else []
        # Full source lines are needed for mixed receipts. Never expense the
        # whole journal just because one line is a Market List item.
        all_items=rows('SELECT * FROM goods_receipt_items WHERE goods_receipt_id=ANY(:ids) ORDER BY goods_receipt_id,id',{'ids':receipt_ids}) if receipt_ids else []
        journal_ids=sorted({m['journal_entry_id'] for m in movements if m['journal_entry_id']})
        journals=rows("SELECT * FROM journal_entries WHERE (reference_type='GOODS_RECEIPT' AND reference_id=ANY(:receipts)) OR id=ANY(:journals) ORDER BY id",{'receipts':receipt_ids,'journals':journal_ids})
        journal_ids=[j['id'] for j in journals]
        lines=rows('SELECT * FROM journal_lines WHERE journal_entry_id=ANY(:ids) ORDER BY journal_entry_id,id',{'ids':journal_ids}) if journal_ids else []
        numbers=[j['journal_number'] for j in journals]
        ledger=rows("SELECT * FROM general_ledger WHERE (reference_type='GOODS_RECEIPT' AND reference_id=ANY(:receipts)) OR reference_number=ANY(:numbers) ORDER BY id",{'receipts':receipt_ids,'numbers':numbers})
        expense=rows("SELECT id,account_number,account_name,account_type,normal_balance,is_active,is_posting FROM chart_of_accounts WHERE account_number='500-100-100'")
        warehouses=rows('SELECT id,code,name,location_id FROM warehouses ORDER BY id')
        review=[]
        for p in products:
            stocks=[s for s in inventory if s['product_id']==p['id']]
            events=[m for m in movements if m['product_id']==p['id']]
            received=[i for i in items if i['product_id']==p['id']]
            flags=[]
            if any(i.get('destination_override_reason') for i in received):flags.append('EXPLICIT_DESTINATION_EXCEPTION')
            if any(str(m['movement_type']).upper()!='IN' or str(m['reference_type']).upper()!='GOODS_RECEIPT' for m in events):flags.append('OTHER_STOCK_HISTORY_REQUIRES_TRACE')
            if any(term in p['name'].upper() for term in ('FROZEN','BEKU','TENDERLOIN','SIRLOIN')):flags.append('POSSIBLE_WAREHOUSE_EXCEPTION')
            if p['inventory_treatment'] in ('FIXED_ASSET','NON_STOCK','REVIEW_REQUIRED'):flags.append('TREATMENT_REVIEW')
            quantity=sum((Decimal(str(s['quantity'])) for s in stocks),Decimal(0))
            value=sum((Decimal(str(s['quantity']))*Decimal(str(s['average_cost'])) for s in stocks),Decimal(0))
            review.append(dict(id=p['id'],code=p['code'],name=p['name'],catalog=p['catalog_type'],family=p['subgroup_name'],
                treatment=p['inventory_treatment'],inventory_coa=p['inventory_coa'],expense_coa=p['expense_coa'],
                quantity=str(quantity),value=str(value.quantize(Decimal('.01'))),stock_rows=len(stocks),
                movement_types=dict(Counter(str(m['movement_type']) for m in events)),
                receipt_ids=sorted({i['goods_receipt_id'] for i in received}),flags=flags))
        evidence=dict(products=products,inventory=inventory,movements=movements,receipts=receipts,
            receipt_items=all_items,journals=journals,journal_lines=lines,general_ledger=ledger,
            expense_account=expense,warehouses=warehouses)
        serialized=json.dumps(evidence,default=str,sort_keys=True)
        report=dict(mode='READ_ONLY',sha256=hashlib.sha256(serialized.encode()).hexdigest(),review=review,evidence=evidence)
        Path(args.output).write_text(json.dumps(report,default=str,indent=2))
        shown=[r for r in review if r['stock_rows']]
        print(json.dumps(dict(mode='READ_ONLY',master_candidates=len(review),stocked_items=len(shown),
            positive_stock_items=sum(Decimal(r['quantity'])>0 for r in shown),
            stock_value=str(sum((Decimal(r['value']) for r in shown),Decimal(0))),
            review_flags=dict(Counter(f for r in shown for f in r['flags'])),expense_account=expense,
            preview=shown[:30],output=args.output),default=str,indent=2))
        db.rollback()
    print('READ ONLY: no item, stock, receiving, journal, GL, tax, AP or opening balance changed.')


if __name__=='__main__':main()
