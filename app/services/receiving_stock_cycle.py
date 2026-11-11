"""Receipt stock cycles retain original INs and explicit depost reversals."""
from collections import defaultdict
from decimal import Decimal
import re

from sqlalchemy import func
from app.models.stock_movement import StockMovement

DEPOST = 'GOODS_RECEIPT_UNPOST'
_REVERSED_MOVEMENT = re.compile(r'^Depost reversal of stock movement (\d+):')


def is_receipt_depost_reversal(db, movement):
    """Only paired system reversals are safe to ignore as *consumption*.

    The reversal still affects stock quantities and inventory valuation. Do not
    exempt arbitrary OUT movements carrying a similar reference type.
    """
    if (movement.reference_type != DEPOST or movement.movement_type != 'OUT'
            or movement.reference_id is None
            or movement.reference_id != movement.goods_receipt_id
            or movement.goods_receipt_item_id is None):
        return False
    match = _REVERSED_MOVEMENT.match(movement.notes or '')
    if not match:
        return False
    source = db.get(StockMovement, int(match.group(1)))
    return bool(
        source and source.id < movement.id
        and source.reference_type == 'GOODS_RECEIPT'
        and source.movement_type == 'IN'
        and source.reference_id == movement.reference_id
        and source.goods_receipt_id == movement.goods_receipt_id
        and source.goods_receipt_item_id == movement.goods_receipt_item_id
        and source.product_id == movement.product_id
        and source.warehouse_id == movement.warehouse_id
        and Decimal(source.quantity) == Decimal(movement.quantity)
        and Decimal(source.unit_cost) == Decimal(movement.unit_cost)
    )


def unsafe_later_receipt_movement(db, *, product_id, warehouse_id, after_id):
    """Find genuine downstream stock usage/adjustments, not other GR reversals."""
    later = (db.query(StockMovement)
             .filter(StockMovement.product_id == product_id,
                     StockMovement.warehouse_id == warehouse_id,
                     StockMovement.id > after_id)
             .order_by(StockMovement.id))
    for movement in later:
        if (movement.movement_type == 'IN' and Decimal(movement.quantity) > 0
                and Decimal(movement.unit_cost) >= 0):
            continue
        if is_receipt_depost_reversal(db, movement):
            continue
        return movement
    return None

def active_receipt_stock(db, receipt_id):
    last = db.query(func.max(StockMovement.id)).filter_by(goods_receipt_id=receipt_id, reference_type=DEPOST).scalar() or 0
    return db.query(StockMovement).filter(StockMovement.goods_receipt_id == receipt_id,
        StockMovement.reference_type == 'GOODS_RECEIPT', StockMovement.movement_type == 'IN', StockMovement.id > last).order_by(StockMovement.id).all()


def draft_stock_is_clear(db, receipt_id):
    balances = defaultdict(Decimal)
    for row in db.query(StockMovement).filter_by(goods_receipt_id=receipt_id):
        if (row.reference_type, row.movement_type) == ('GOODS_RECEIPT', 'IN'):
            balances[(row.product_id,row.warehouse_id)] += Decimal(row.quantity)
        elif (row.reference_type, row.movement_type) == (DEPOST, 'OUT'):
            balances[(row.product_id,row.warehouse_id)] -= Decimal(row.quantity)
        else:
            return False
    return all(value == 0 for value in balances.values())
