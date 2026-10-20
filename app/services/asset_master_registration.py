"""Automatic unvalued asset-register intake from classified Item Master records."""
from sqlalchemy import event, func, null
from sqlalchemy.orm import Session
from fastapi import HTTPException


def register_master_asset(db, product):
    from app.services.item_asset_policy import validate_asset_item
    validate_asset_item(product)
    from app.models.fixed_asset import FixedAsset
    from app.models.chart_of_account import ChartOfAccount
    from app.models.audit_log import AuditLog
    if product.item_type != 'BUY' or not product.is_active or product.inventory_treatment != 'FIXED_ASSET': return None
    account = db.get(ChartOfAccount, product.asset_account_id) if product.asset_account_id else None
    if not account or not account.is_active or not account.is_posting or account.account_type != 'ASSET' or account.normal_balance != 'DEBIT' or not account.account_number.startswith(('100-600-', '100-900-')):
        raise HTTPException(422, 'Fixed asset items require a posting 100-600 or 100-900 asset account')
    existing = db.query(FixedAsset).filter(FixedAsset.product_id == product.id).order_by(FixedAsset.id).all()
    if existing:
        if any(a.status != "PENDING_REGISTRATION" and a.asset_account_id != product.asset_account_id for a in existing):
            raise HTTPException(409, "Registered asset account differs; correct the asset/source accounting before changing Item Master")
        pending = [a for a in existing if a.status == 'PENDING_REGISTRATION' and a.source_type == 'ITEM_MASTER']
        for asset in pending:
            asset.asset_name = product.name
            asset.asset_account_id = product.asset_account_id
        return existing[0]
    from app.models.business_unit import BusinessUnit
    unit_name = 'HOTEL' if product.catalog_type == 'HOTEL' else 'PROJECT CATERING'
    units = db.query(BusinessUnit).filter(BusinessUnit.is_active.is_(True), func.upper(func.trim(BusinessUnit.name)) == unit_name).limit(2).all()
    asset = FixedAsset(asset_number=f'FA-ITEM-{product.id:08d}', asset_name=product.name,
        product_id=product.id, asset_account_id=product.asset_account_id,
        status='PENDING_REGISTRATION', source_type='ITEM_MASTER',
        acquisition_date=None, acquisition_cost=None, net_book_value=null(),
        business_unit_id=units[0].id if len(units) == 1 else None, created_by_id=None)
    db.add(asset)
    db.add(AuditLog(action='ASSET_MASTER_AUTO_REGISTERED', entity_type='PRODUCT', entity_id=product.id,
        summary=f'Automatically register asset item {product.code}',
        after_data={'product_id': product.id, 'asset_number': asset.asset_number, 'asset_account_id': product.asset_account_id,
                    'status': 'PENDING_REGISTRATION'},
        details={'module': 'Fixed Assets', 'source': 'Item Master', 'accounting_created': False, 'valuation_pending': True}))
    return asset


@event.listens_for(Session, 'before_flush')
def collect_asset_items(db, _context, _instances):
    from app.models.product import Product
    rows = [p for p in set(db.new).union(db.dirty) if isinstance(p, Product)
            and not getattr(p, '_asset_intake_item', False)
            and p.inventory_treatment == 'FIXED_ASSET']
    if rows: db.info.setdefault('asset_master_queue', []).extend(rows)


@event.listens_for(Session, 'after_flush_postexec')
def register_asset_items(db, _context):
    for product in db.info.pop('asset_master_queue', []): register_master_asset(db, product)


@event.listens_for(Session, 'after_soft_rollback')
def clear_asset_queue(db, _previous):
    db.info.pop('asset_master_queue', None)
