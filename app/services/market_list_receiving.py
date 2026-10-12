"""Remaining ML quantities shared by direct receiving and PO conversion."""
from decimal import Decimal
from sqlalchemy import func
from app.models.goods_receipt import GoodsReceipt, GoodsReceiptItem
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem


def allocated_market_items(db, market_list_id, exclude_receipt_id=None):
    orders = dict(db.query(PurchaseOrderItem.market_list_item_id, func.sum(PurchaseOrderItem.quantity))
        .join(PurchaseOrder).filter(PurchaseOrder.market_list_id==market_list_id,
            PurchaseOrder.status.notin_(['CANCELLED','REJECTED','ARCHIVED']))
        .group_by(PurchaseOrderItem.market_list_item_id).all())
    receipts = db.query(GoodsReceiptItem.market_list_item_id,func.sum(GoodsReceiptItem.quantity)).join(GoodsReceipt).filter(
        GoodsReceipt.market_list_id==market_list_id, GoodsReceipt.status.in_(['DRAFT','POSTED']))
    if exclude_receipt_id:
        receipts=receipts.filter(GoodsReceipt.id!=exclude_receipt_id)
    for item_id, amount in receipts.group_by(GoodsReceiptItem.market_list_item_id).all():
        orders[item_id]=Decimal(orders.get(item_id,0))+Decimal(amount or 0)
    return orders
