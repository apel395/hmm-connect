"""Reclassify the 35 inspected Hotel linen masters and remove empty asset intake.

Preview by default. No opening quantities, movements, depreciation or journals
are created. The original item IDs, units, prices, tax and supplier links remain.
"""
import argparse
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import or_, select
from app.models import Base
from app.models.sales_transaction import SalesTransaction  # noqa: F401 - register POS/AR FKs for standalone inspection
from app.models.product import Product
from app.models.chart_of_account import ChartOfAccount
from app.models.fixed_asset import FixedAsset
from app.models.item_group import ItemGroup
from app.models.item_subgroup import ItemSubgroup
from app.models.audit_log import AuditLog
from app.models.journal_entry import JournalEntry
from app.models.general_ledger import GeneralLedger
from app.services.item_asset_policy import is_linen
from app.services.item_code import lock_item_creation, next_item_code
from app.services.audit import record_audit
from scripts.reclassify_hotel_utensils_1020 import snapshot, account, no_item_activity

BATCH = 'HOTEL_LINEN_20261102'
# Exact IDs from the EC2 read-only report: asset IDs 3..37 / product IDs 7344..7378.
TARGETS = tuple((pid, pid-7341) for pid in range(7344, 7379))
FIELDS = ('code','group_code','group_name','subgroup_code','subgroup_name',
          'inventory_treatment','inventory_account_id','asset_account_id')


def empty_asset(db, product, asset, expected_id):
    if asset.id != expected_id or asset.asset_number != f'FA-ITEM-{product.id:08d}':
        raise ValueError('asset identity differs from the inspected registration')
    if asset.status != 'PENDING_REGISTRATION' or asset.source_type != 'ITEM_MASTER':
        raise ValueError('asset has been registered or its source changed')
    if asset.asset_account_id != product.asset_account_id:
        raise ValueError('asset and master accounts differ')
    for key in ('acquisition_cost','acquisition_date','capitalization_date','asset_category_id','useful_life_months',
                'depreciation_start_date','serial_number','barcode','custodian_user_id','supplier_id',
                'purchase_invoice_id','source_invoice_line_id','purchase_order_id','goods_receipt_id','disposed_at','written_off_at'):
        if getattr(asset,key) is not None:
            raise ValueError(f'asset has {key}; inspection required')
    for key in ('net_book_value','accumulated_depreciation','residual_value','quantity'):
        if getattr(asset,key) not in (None,0):
            raise ValueError(f'asset has {key}; inspection required')
    # Check every registered FK before ORM deletion (whose cascade must not erase history).
    for table in Base.metadata.tables.values():
        for col in table.columns:
            if any(f.target_fullname=='fixed_assets.id' for f in col.foreign_keys):
                if db.execute(select(col).where(col==asset.id).limit(1)).first():
                    raise ValueError(f'asset has evidence in {table.name}')
    direct_types=('FIXED_ASSET','FIXED_ASSET_CAPITALIZATION','FIXED_ASSET_DISPOSAL','FIXED_ASSET_WRITE_OFF','FIXED_ASSET_TRANSFER')
    for model in (JournalEntry,GeneralLedger):
        if db.query(model.id).filter(or_(
            (model.reference_type.in_(direct_types)) & (model.reference_id==asset.id),
            model.document_number==asset.asset_number,
        )).first():
            raise ValueError(f'asset has accounting evidence in {model.__tablename__}')


def material_linen_subgroup(db, actor):
    groups=db.query(ItemGroup).filter(ItemGroup.code=='3',ItemGroup.name=='MATERIAL',ItemGroup.is_active.is_(True),
        ItemGroup.item_type.in_(('BUY','ITEM'))).order_by(ItemGroup.id).with_for_update().all()
    # Prefer the explicit BUY catalog; ITEM is the supported legacy purchasing type.
    buy=[g for g in groups if g.item_type=='BUY']
    eligible=buy or groups
    if len(eligible)!=1:
        raise ValueError('Active purchasing MATERIAL group 3 is not uniquely configured')
    group=eligible[0]
    subs=db.query(ItemSubgroup).order_by(ItemSubgroup.id).with_for_update().all()
    matches=[s for s in subs if s.group_id==group.id and s.name.strip().upper()=='LINEN']
    if len(matches)>1 or (matches and not matches[0].is_active):
        raise ValueError('MATERIAL / LINEN subgroup is not uniquely active')
    if matches:
        subgroup=matches[0]
        if not re.fullmatch(r'3-\d+',subgroup.code):
            raise ValueError('LINEN subgroup must use the registered numeric MATERIAL code format')
        return group,subgroup
    occupied={s.code for s in subs}
    number=max((int(s.code[2:]) for s in subs if re.fullmatch(r'3-\d+',s.code)),default=0)+1
    while f'3-{number}' in occupied: number+=1
    code=f'3-{number}'
    if len(code)>10: raise ValueError('MATERIAL subgroup code range exhausted')
    subgroup=ItemSubgroup(code=code,name='LINEN',group_id=group.id,is_active=True)
    db.add(subgroup);db.flush()
    audit=record_audit(db,actor,'ITEM_SUBGROUP_CREATED','ITEM_SUBGROUP',f'Create {code} LINEN',entity_id=subgroup.id,
        after_data={'code':code,'name':'LINEN','group_id':group.id},details={'batch':BATCH})
    audit.source='SYSTEM'
    return group,subgroup


def cleanup(db):
    lock_item_creation(db)
    pending=[];done=[];problems=[]
    # Do not create a subgroup or mutate any record until all 35 targets pass.
    for pid,aid in TARGETS:
        try:
            p=db.query(Product).filter_by(id=pid).with_for_update().one_or_none()
            if p is None: raise ValueError('item is missing')
            assets=db.query(FixedAsset).filter(FixedAsset.product_id==pid).order_by(FixedAsset.id).with_for_update().all()
            previous=db.query(AuditLog).filter_by(action='LINEN_RECLASSIFIED',entity_type='PRODUCT',entity_id=pid).order_by(AuditLog.id.desc()).first()
            if previous and (previous.details or {}).get('batch')==BATCH:
                after=previous.after_data or {}
                if assets or any(getattr(p,k)!=after.get(k) for k in FIELDS):
                    raise ValueError('previously cleaned classification/asset links changed')
                # New legitimate receipts/issues after cleanup do not invalidate a no-op rerun.
                done.append(pid);continue
            if not p.is_active or p.item_type!='BUY' or p.catalog_type!='HOTEL' or not is_linen(p):
                raise ValueError('not the inspected active Hotel BUY linen')
            if p.inventory_treatment!='FIXED_ASSET' or p.group_code!='4' or p.group_name!='ASSET':
                raise ValueError('source classification changed without this cleanup audit')
            coa=db.get(ChartOfAccount,p.asset_account_id)
            if not coa or coa.account_number!='100-900-100':
                raise ValueError('source account is not 100-900-100 linen')
            if len(assets)!=1: raise ValueError('missing or multiple asset links')
            empty_asset(db,p,assets[0],aid)
            no_item_activity(db,p)
            pending.append((p,assets[0]))
        except ValueError as exc:
            problems.append(f'Item {pid}: {exc}')
    if problems:
        raise ValueError('Cleanup stopped before changes:\n'+'\n'.join(problems))
    if not pending:
        return {'batch':BATCH,'target_items':len(TARGETS),'already_applied':len(done),'changed_items':0,'removed_empty_assets':0,'items':[]}
    inventory=account(db,'100-900-100','ASSET')
    actor=SimpleNamespace(id=None,full_name='EC2 inspected Hotel linen cleanup',roles=[])
    group,subgroup=material_linen_subgroup(db,actor)
    changes=[]
    for p,asset in pending:
        before=snapshot(p);asset_before=snapshot(asset)
        p.code=next_item_code(db,group.code,subgroup.code)
        p.group_code=group.code;p.group_name=group.name
        p.subgroup_code=subgroup.code;p.subgroup_name=subgroup.name
        p.inventory_treatment='STOCK';p.inventory_account_id=inventory.id;p.asset_account_id=None
        # Preserve UOM/conversion, department/supplier links, prices and tax; no invented issue-expense mapping.
        db.delete(asset)
        audit=record_audit(db,actor,'LINEN_RECLASSIFIED','PRODUCT',f'Reclassify {before["code"]} to {p.code}',entity_id=p.id,
            before_data=before,after_data=snapshot(p),details={'batch':BATCH,'removed_unvalued_asset':asset_before,
            'stock_or_accounting_created':False})
        audit.source='SYSTEM';db.flush()
        changes.append({'id':p.id,'name':p.name,'old_code':before['code'],'new_code':p.code,'removed_asset_id':asset_before['id'],
                        'unit':p.uom,'usage_unit':p.usage_uom,'conversion':str(p.conversion),
                        'purchase_account_id':p.purchase_account_id,'cogs_account_id':p.cogs_account_id})
    return {'batch':BATCH,'target_items':len(TARGETS),'already_applied':len(done),'changed_items':len(changes),'removed_empty_assets':len(changes),
        'group':group.name,'subgroup':subgroup.name,'treatment':'STOCK','inventory_account':inventory.account_number,'items':changes}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    from app.core.database import SessionLocal
    with SessionLocal() as db:
        try:
            result=cleanup(db)
            if args.apply: db.commit()
            else: db.rollback()
        except Exception:
            db.rollback()
            raise
    print(json.dumps({'mode':'APPLY' if args.apply else 'DRY_RUN',**result},indent=2))
    print('ALREADY APPLIED: linen classification and empty asset removal verified. No writes.' if not result['changed_items'] else 'COMMITTED linen master classification and deletion of empty pending asset registrations only.' if args.apply else 'DRY RUN: all changes rolled back.')
    print('Stock quantities, prices, UOM, tax, source documents, journals and opening balances unchanged.')


if __name__=='__main__':main()
