"""User-directed fresh-food Item Master correction. Dry-run rolls back all changes.

Keeps frozen/tenderloin/imported warehouse defaults. Other listed food families
become Direct Use using an existing expense mapping or registered food-cost COA.
Only proven receiving-only false stock is repaired automatically. Blocked items
stay unchanged and are listed for separate correction. Tax/AP/openings untouched.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--output',default='/tmp/food-treatment-correction.json')
    args=parser.parse_args()
    from sqlalchemy import func
    from app.core.database import SessionLocal
    from app.models.product import Product
    from app.models.chart_of_account import ChartOfAccount
    from app.models.inventory import Inventory
    from app.services.item_treatment_policy import DIRECT_USE_FAMILIES,food_treatment
    from app.services.item_treatment_correction import correct_receiving_only_stock,snapshot
    from app.services.audit import record_audit
    from fastapi import HTTPException
    actor=SimpleNamespace(id=None,full_name='EC2 food classification operator',username=None,roles=[SimpleNamespace(name='SYSTEM_ADMINISTRATOR')],audit_source='EC2_SCRIPT')
    results=[]
    with SessionLocal() as db:
        try:
            if db.bind.dialect.name=='postgresql':
                from sqlalchemy import text
                db.execute(text("SET LOCAL lock_timeout='5s'"))
                db.execute(text("SET LOCAL statement_timeout='60s'"))
                db.execute(text('SELECT pg_advisory_xact_lock(484017,1017)'))
            products=db.query(Product).filter(Product.item_type=='BUY',func.upper(func.trim(Product.group_name))=='FOOD',func.upper(func.trim(Product.subgroup_name)).in_(DIRECT_USE_FAMILIES)).order_by(Product.id).with_for_update().all()
            fallback=db.query(ChartOfAccount).filter_by(account_number='500-100-100').first()
            for p in products:
                result=dict(id=p.id,code=p.code,name=p.name,previous_treatment=p.inventory_treatment)
                if food_treatment(p.subgroup_name,p.name)=='STOCK':
                    results.append({**result,'status':'PRESERVE_WAREHOUSE_EXCEPTION'});continue
                if p.inventory_treatment not in {'STOCK','DIRECT_USE','REVIEW_REQUIRED'}:
                    results.append({**result,'status':'BLOCKED','reason':'Nonstandard treatment requires review'});continue
                has_rows=db.query(Inventory.id).filter_by(product_id=p.id).first() is not None
                current_expense=db.get(ChartOfAccount,p.purchase_account_id) if p.purchase_account_id else None
                if p.inventory_treatment=='DIRECT_USE' and not has_rows and current_expense and current_expense.is_active and current_expense.is_posting and current_expense.account_type=='EXPENSE' and current_expense.normal_balance=='DEBIT' and p.is_market_item and not any((p.inventory_account_id,p.cogs_account_id,p.asset_account_id)):
                    results.append({**result,'status':'ALREADY_DIRECT_USE'});continue
                savepoint=db.begin_nested()
                try:
                    candidates=[db.get(ChartOfAccount,aid) for aid in (p.purchase_account_id,p.cogs_account_id) if aid]
                    if fallback:candidates.append(fallback)
                    expense=next((a for a in candidates if a and a.is_active and a.is_posting and a.account_type=='EXPENSE' and a.normal_balance=='DEBIT'),None)
                    if not expense:raise HTTPException(409,'No valid registered food expense account')
                    old=snapshot(p)
                    correction=correct_receiving_only_stock(db,p,expense_account_id=expense.id,user=actor,reason='Correct fresh-food Item Master and false receiving stock per 10-15 note') if has_rows else {'corrected_receipts':[],'removed_stock_rows':0}
                    p.inventory_treatment='DIRECT_USE';p.purchase_account_id=expense.id
                    p.inventory_account_id=None;p.cogs_account_id=None;p.asset_account_id=None;p.is_market_item=True
                    audit=record_audit(db,actor,'FOOD_ITEM_TREATMENT_CORRECTED','PRODUCT',f'Set {p.code} to Direct Use',entity_id=p.id,before_data=json.loads(json.dumps(old,default=str)),after_data={'inventory_treatment':'DIRECT_USE','purchase_account_id':expense.id},details={'executor':'EC2_SCRIPT','tax_unchanged':True})
                    audit.source='EC2_SCRIPT'
                    db.flush()
                    savepoint.commit()
                    results.append({**result,'status':'CORRECT','expense_account':expense.account_number,**correction})
                except HTTPException as error:
                    savepoint.rollback()
                    results.append({**result,'status':'BLOCKED','reason':error.detail})
            report=dict(mode='APPLY' if args.apply else 'DRY_RUN',counts=dict(Counter(r['status'] for r in results)),items=results)
            Path(args.output).write_text(json.dumps(report,default=str,indent=2))
            if args.apply:db.commit()
            else:db.rollback()
            print(json.dumps({**{k:v for k,v in report.items() if k!='items'},'blocked':[r for r in results if r['status']=='BLOCKED'],'output':args.output},default=str,indent=2))
            print('COMMITTED eligible master/source corrections.' if args.apply else 'DRY RUN: all changes rolled back. Use --apply to commit eligible items.')
            print('No synthetic OUT, extra journal, tax/AP/opening-balance changes.')
        except Exception:
            db.rollback();raise


if __name__=='__main__':main()
