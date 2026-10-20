"""Repair the 13 inspected, unvalued Hotel utensil registrations. Preview by default."""
import argparse
from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from app.models import Base
from app.models.product import Product
from app.models.item_group import ItemGroup
from app.models.item_subgroup import ItemSubgroup
from app.models.chart_of_account import ChartOfAccount
from app.models.inventory import Inventory
from app.models.fixed_asset import FixedAsset, FixedAssetMovement, FixedAssetDepreciationSchedule
from app.models.journal_entry import JournalEntry
from app.models.general_ledger import GeneralLedger
from app.models.audit_log import AuditLog
from app.services.item_code import lock_item_creation, next_item_code
from app.services.audit import record_audit

BATCH='HOTEL_UTENSILS_20261020'
# (product ID, old code, exact inspected name, pending asset ID, old account)
TARGETS=(
    (7391,'4-200049','CHI - Tea Cup & Saucer Indokramik',50,'100-900-101'),
    (7399,'4-200057','UTEN - Dessert Fork',58,'100-900-102'),
    (7400,'4-200058',"UTEN - Dessert Fork Sedang 'Silvana'",59,'100-900-102'),
    (7401,'4-200059',"UTEN - Dessert Spoon Sedang ' Silvana'",60,'100-900-102'),
    (7402,'4-200060','UTEN - Dinner Fork Besar " Silvana "',61,'100-900-102'),
    (7403,'4-200061','UTEN - Dinner Spoon Besar " Silvana "',62,'100-900-102'),
    (7404,'4-200062','UTEN - Dinner Spoon Stainless',63,'100-900-102'),
    (7405,'4-200063','UTEN - Piring B&B 6 Inchi',64,'100-900-101'),
    (7406,'4-200064','UTEN - Sendok Dessert Spoon Super Bold',65,'100-900-102'),
    (7407,'4-200065','UTEN - Soup Cup & Saucer Indokramik',66,'100-900-101'),
    (7408,'4-200066','UTEN - Soup Spoon',67,'100-900-102'),
    (7409,'4-200067','UTEN - Soup Spoon Royal',68,'100-900-102'),
    (7410,'4-200068',"UTEN - Tea Spoon 'VVC066-3'",69,'100-900-102'),
)
FIELDS=('code','group_code','group_name','subgroup_code','subgroup_name','inventory_treatment','inventory_account_id','purchase_account_id','cogs_account_id','asset_account_id')


def snapshot(row):
    return {c.name:(str(v) if isinstance(v,Decimal) else v.isoformat() if isinstance(v,(date,datetime)) else v)
        for c in row.__table__.columns for v in [getattr(row,c.name)]}


def account(db,code,kind):
    rows=db.query(ChartOfAccount).filter(ChartOfAccount.account_number==code).with_for_update().all()
    if len(rows)!=1 or not rows[0].is_active or not rows[0].is_posting or rows[0].account_type!=kind or rows[0].normal_balance!='DEBIT':
        raise ValueError(f'Active debit posting {kind} account {code} is required')
    return rows[0]


def no_item_activity(db,product):
    for stock in db.query(Inventory).filter_by(product_id=product.id).with_for_update():
        if stock.quantity or stock.average_cost:raise ValueError(f'Item {product.id} has stock quantity/value; inspection required')
    # Preserve all master references. Any transactional product link, even draft,
    # means the read-only evidence has changed and requires another inspection.
    masters={'products','inventory','fixed_assets','item_departments','supplier_products'}
    for table in Base.metadata.sorted_tables:
        if table.name in masters:continue
        for column in table.columns:
            if any(f.target_fullname=='products.id' for f in column.foreign_keys):
                if db.execute(select(column).where(column==product.id).limit(1)).first():
                    raise ValueError(f'Item {product.id} has activity in {table.name}; no repair applied')


def repair(db, targets=TARGETS):
    lock_item_creation(db)
    # Validate the entire batch before creating classifications or changing rows.
    rows=[];done=[]
    for pid,old_code,name,aid,old_account in targets:
        product=db.query(Product).filter_by(id=pid).with_for_update().one_or_none()
        if not product or product.name!=name or product.item_type!='BUY' or product.catalog_type!='HOTEL' or not product.is_active:
            raise ValueError(f'Item {pid} no longer matches the inspected active Hotel BUY item')
        no_item_activity(db,product)
        assets=db.query(FixedAsset).filter_by(product_id=pid).with_for_update().all()
        audit=db.query(AuditLog).filter_by(entity_type='PRODUCT',entity_id=pid,action='UTENSIL_RECLASSIFIED').order_by(AuditLog.id.desc()).first()
        if audit and (audit.details or {}).get('batch')==BATCH:
            after=audit.after_data or {}
            if assets or any(getattr(product,k)!=after.get(k) for k in FIELDS):
                raise ValueError(f'Previously repaired item {pid} changed; inspection required')
            done.append(pid);continue
        old_coa=db.get(ChartOfAccount,product.asset_account_id)
        if product.code!=old_code or product.group_code!='4' or product.group_name!='ASSET' or product.inventory_treatment!='FIXED_ASSET' or not old_coa or old_coa.account_number!=old_account:
            raise ValueError(f'Item {pid} classification no longer matches the inspected source')
        if len(assets)!=1 or assets[0].id!=aid:
            raise ValueError(f'Item {pid} asset links changed')
        asset=assets[0]
        if (asset.asset_number!=f'FA-ITEM-{pid:08d}' or asset.status!='PENDING_REGISTRATION' or asset.source_type!='ITEM_MASTER'
            or asset.asset_account_id!=product.asset_account_id or asset.acquisition_cost is not None
            or asset.acquisition_date is not None or asset.capitalization_date is not None
            or asset.net_book_value not in (None,0) or asset.accumulated_depreciation not in (None,0)
            or asset.residual_value not in (None,0) or asset.quantity not in (None,0)
            or any(getattr(asset,k) is not None for k in ('asset_category_id','useful_life_months','depreciation_start_date','serial_number','barcode','custodian_user_id'))
            or any(getattr(asset,k) is not None for k in ('purchase_invoice_id','source_invoice_line_id','purchase_order_id','goods_receipt_id'))):
            raise ValueError(f'Asset {aid} is valued, registered or linked; no repair applied')
        if db.query(FixedAssetMovement).filter_by(fixed_asset_id=aid).first() or db.query(FixedAssetDepreciationSchedule).filter_by(fixed_asset_id=aid).first():
            raise ValueError(f'Asset {aid} has movement/depreciation history')
        for model in (JournalEntry,GeneralLedger):
            if db.query(model).filter(model.reference_type.in_(('FIXED_ASSET','FIXED_ASSET_CAPITALIZATION','FIXED_ASSET_DISPOSAL','FIXED_ASSET_WRITE_OFF')),model.reference_id==aid).first():
                raise ValueError(f'Asset {aid} has accounting evidence')
        rows.append((product,asset))
    if not rows:return {'batch':BATCH,'already_applied':len(done),'changed_items':0,'removed_empty_assets':0,'items':[]}
    inventory=account(db,'100-300-700','ASSET')
    expense=account(db,'700-500-119','EXPENSE')
    groups=db.query(ItemGroup).filter_by(code='3',name='MATERIAL',is_active=True).with_for_update().all()
    if len(groups)!=1 or groups[0].item_type not in ('BUY','ITEM'):
        raise ValueError('Active MATERIAL BUY group 3 is not uniquely configured')
    group=groups[0]
    subgroups=db.query(ItemSubgroup).with_for_update().all()
    matches=[s for s in subgroups if s.group_id==group.id and s.name.strip().upper()=='UTENSILS']
    if len(matches)>1 or (matches and not matches[0].is_active):raise ValueError('UTENSILS subgroup is not uniquely active')
    actor=SimpleNamespace(id=None,full_name='EC2 inspected utensil correction',roles=[])
    if matches:
        subgroup=matches[0]
        if not re.fullmatch(r'3-\d+',subgroup.code):raise ValueError('UTENSILS subgroup must use the registered numeric MATERIAL format')
    else:
        occupied={s.code for s in subgroups}
        sequence=max((int(s.code[2:]) for s in subgroups if re.fullmatch(r'3-\d+',s.code)),default=0)+1
        code=f'3-{sequence}'
        while code in occupied:sequence+=1;code=f'3-{sequence}'
        if len(code)>10:raise ValueError('MATERIAL subgroup code range exhausted')
        subgroup=ItemSubgroup(code=code,name='UTENSILS',group_id=group.id,is_active=True)
        db.add(subgroup);db.flush()
        audit=record_audit(db,actor,'ITEM_SUBGROUP_CREATED','ITEM_SUBGROUP',f'Create {subgroup.code} UTENSILS',
            entity_id=subgroup.id,after_data={'code':subgroup.code,'name':subgroup.name,'group_id':group.id},details={'batch':BATCH})
        audit.source='EC2_SCRIPT'
    changes=[]
    for product,asset in rows:
        before=snapshot(product);asset_before=snapshot(asset)
        product.code=next_item_code(db,group.code,subgroup.code)
        product.group_code=group.code;product.group_name=group.name
        product.subgroup_code=subgroup.code;product.subgroup_name=subgroup.name
        product.inventory_treatment='STOCK';product.inventory_account_id=inventory.id
        product.purchase_account_id=None;product.cogs_account_id=expense.id;product.asset_account_id=None
        db.delete(asset)
        audit=record_audit(db,actor,'UTENSIL_RECLASSIFIED','PRODUCT',f'Reclassify {before["code"]} to {product.code}',
            entity_id=product.id,before_data=before,after_data=snapshot(product),details={'batch':BATCH,'removed_unvalued_asset':asset_before,'stock_or_accounting_created':False})
        audit.source='EC2_SCRIPT'
        db.flush()
        changes.append({'id':product.id,'name':product.name,'old_code':before['code'],'new_code':product.code,'removed_asset_id':asset_before['id']})
    return {'batch':BATCH,'already_applied':len(done),'changed_items':len(changes),'removed_empty_assets':len(changes),
        'group':'MATERIAL','subgroup':subgroup.name,'treatment':'STOCK','inventory_account':inventory.account_number,
        'issue_expense_account':expense.account_number,'items':changes}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    from app.core.database import SessionLocal
    with SessionLocal() as db:
        result=repair(db)
        if args.apply:db.commit()
        else:db.rollback()
    print(json.dumps({'mode':'APPLY' if args.apply else 'DRY_RUN',**result},indent=2))
    print('COMMITTED inspected item classification and empty asset removal. No stock, tax or accounting changes.' if args.apply else 'DRY RUN: all changes rolled back.')

if __name__=='__main__':main()
