"""Receipt stock cycles retain original INs and explicit depost reversals."""
from collections import defaultdict
from decimal import Decimal
from sqlalchemy import func
from app.models.stock_movement import StockMovement

DEPOST = 'GOODS_RECEIPT_UNPOST'

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
