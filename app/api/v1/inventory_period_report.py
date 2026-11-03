from app.services.stock_movement_value import sql_movement_value, sql_signed_movement_value
from datetime import date
from math import ceil
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, case, func, or_, select, union
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.warehouse import Warehouse
from app.models.location import Location
from app.models.stock_movement import StockMovement
from app.models.goods_receipt import GoodsReceipt
from app.services.location_access import apply_warehouse_scope
from app.services.organization_access import resolve_organization_access
from app.api.v1.inventory import _effective_movement_date

router = APIRouter(prefix='/inventory/period-report', tags=['Inventory Reports'])


@router.get('')
def period_report(date_from: date, date_to: date, warehouse_id: int | None = None,
                  business_unit_id: int | None = None, location_id: int | None = None,
                  search: str | None = None, page: int = Query(1, ge=1),
                  page_size: int = Query(50, ge=1, le=100), db=Depends(get_db), user=Depends(get_current_user)):
    if date_from > date_to:
        raise HTTPException(422, 'From date must not exceed To date')
    scope = resolve_organization_access(db, user, location_id=location_id, business_unit_id=business_unit_id)
    keys = union(select(Inventory.product_id, Inventory.warehouse_id),
                 select(StockMovement.product_id, StockMovement.warehouse_id)).subquery()
    event_date = _effective_movement_date()
    incoming = case((StockMovement.movement_type == 'IN', func.abs(StockMovement.quantity)), else_=0)
    outgoing = case((StockMovement.movement_type == 'OUT', func.abs(StockMovement.quantity)), else_=0)
    signed = incoming - outgoing
    event_value = sql_signed_movement_value()
    incoming_value = case((StockMovement.movement_type == "IN", sql_movement_value()), else_=0)
    outgoing_value = case((StockMovement.movement_type == "OUT", sql_movement_value()), else_=0)
    within = and_(event_date >= date_from, event_date <= date_to)
    later = event_date > date_to
    source = StockMovement.reference_type
    expressions = {
        'in_quantity': func.sum(case((within, incoming), else_=0)),
        'out_quantity': func.sum(case((within, outgoing), else_=0)),
        'in_value': func.sum(case((within, incoming_value), else_=0)),
        'out_value': func.sum(case((within, outgoing_value), else_=0)),
        'later_quantity': func.sum(case((later, signed), else_=0)),
        'later_value': func.sum(case((later, event_value), else_=0)),
    }
    groups = {
        'receiving': source == 'GOODS_RECEIPT',
        'operational': source == 'STORE_REQUEST',
        'return': source.in_(['GOODS_RECEIPT_RETURN', 'SUPPLIER_RETURN', 'SUPPLIER_RETURN_REVERSAL']),
        'replacement': source == 'SUPPLIER_REPLACEMENT',
        'adjustment': source.in_(['STOCK_ADJUSTMENT', 'STOCK_OPNAME']),
    }
    known = or_(*groups.values())
    groups['other'] = or_(~known, source.is_(None))
    for name, condition in groups.items():
        expressions[name + '_quantity'] = func.sum(case((and_(within, condition), signed), else_=0))
        expressions[name + '_value'] = func.sum(case((and_(within, condition), event_value), else_=0))
    expressions['first_movement_id'] = func.min(StockMovement.id)
    movements = db.query(StockMovement.product_id.label('product_id'), StockMovement.warehouse_id.label('warehouse_id'),
        *[value.label(name) for name, value in expressions.items()]).outerjoin(GoodsReceipt,
        GoodsReceipt.id == StockMovement.goods_receipt_id).group_by(StockMovement.product_id, StockMovement.warehouse_id).subquery()
    q = db.query(Product, Warehouse, Inventory, *[func.coalesce(movements.c[name], 0).label(name) for name in expressions])
    q = q.select_from(keys).join(Product, Product.id == keys.c.product_id).join(Warehouse, Warehouse.id == keys.c.warehouse_id)
    q = q.outerjoin(Location, Location.id == Warehouse.location_id).outerjoin(Inventory,
        and_(Inventory.product_id == keys.c.product_id, Inventory.warehouse_id == keys.c.warehouse_id)).outerjoin(movements,
        and_(movements.c.product_id == keys.c.product_id, movements.c.warehouse_id == keys.c.warehouse_id))
    q = apply_warehouse_scope(q, user)
    if scope['business_unit_id'] is not None:
        q = q.filter(Location.business_unit_id == scope['business_unit_id'])
    if scope['location_id'] is not None:
        q = q.filter(Warehouse.location_id == scope['location_id'])
    if warehouse_id:
        q = q.filter(Warehouse.id == warehouse_id)
    if search and search.strip():
        q = q.filter(or_(Product.code.ilike(f'%{search.strip()}%'), Product.name.ilike(f'%{search.strip()}%')))
    closing_qty = func.coalesce(Inventory.quantity, 0) - func.coalesce(movements.c.later_quantity, 0)
    closing_value = func.coalesce(Inventory.quantity, 0) * func.coalesce(Inventory.average_cost, 0) - func.coalesce(movements.c.later_value, 0)
    opening_qty = closing_qty - func.coalesce(movements.c.in_quantity, 0) + func.coalesce(movements.c.out_quantity, 0)
    opening_value = closing_value - func.coalesce(movements.c.in_value, 0) + func.coalesce(movements.c.out_value, 0)
    q = q.filter(or_(opening_qty != 0, closing_qty != 0, func.coalesce(movements.c.in_quantity, 0) != 0,
                     func.coalesce(movements.c.out_quantity, 0) != 0, opening_value != 0, closing_value != 0))
    total = q.count()
    summary = q.with_entities(func.coalesce(func.sum(opening_value), 0),
        func.coalesce(func.sum(movements.c.in_value), 0), func.coalesce(func.sum(movements.c.out_value), 0),
        func.coalesce(func.sum(closing_value), 0)).one()
    # Never sum quantities across KG, PCS, LTR, etc.
    by_uom = q.with_entities(Product.uom, func.sum(opening_qty), func.sum(movements.c.in_quantity),
        func.sum(movements.c.out_quantity), func.sum(closing_qty)).group_by(Product.uom).all()
    rows = []
    from decimal import Decimal
    for result in q.order_by(Warehouse.code, Product.code, Product.id).offset((page - 1) * page_size).limit(page_size):
        product, warehouse, inventory, *values = result
        stats = dict(zip(expressions, values))
        quantity = Decimal(inventory.quantity or 0) if inventory else Decimal('0')
        value = quantity * Decimal(inventory.average_cost or 0) if inventory else Decimal('0')
        closing = quantity - stats.pop('later_quantity')
        end_value = value - stats.pop('later_value')
        first_id = stats.pop('first_movement_id')
        rows.append({'id': inventory.id if inventory else -int(first_id), 'product_id': product.id, 'product_code': product.code, 'product_name': product.name,
            'warehouse_id': warehouse.id, 'warehouse': warehouse.name, 'uom': product.uom,
            **stats, 'opening_quantity': closing - stats['in_quantity'] + stats['out_quantity'],
            'closing_quantity': closing, 'opening_value': end_value - stats['in_value'] + stats['out_value'],
            'closing_value': end_value, 'missing_inventory_snapshot': inventory is None})
    return {'items': rows, 'total_items': total, 'total_pages': ceil(total / page_size),
        'summary': dict(zip(('opening_value', 'in_value', 'out_value', 'closing_value'), summary)),
        'quantity_totals_by_uom': [{'uom': uom, 'opening': opening or 0, 'in_quantity': inc or 0,
                                  'out_quantity': out or 0, 'closing': closing or 0} for uom, opening, inc, out, closing in by_uom],
        'basis': 'CURRENT_SNAPSHOT_ROLLED_BACK_BY_RECORDED_MOVEMENTS'}
