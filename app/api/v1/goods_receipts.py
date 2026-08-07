from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_any_role
from app.models.goods_receipt import GoodsReceipt
from app.models.purchase_order import PurchaseOrder
from app.schemas.goods_receipt import GoodsReceiptCreate
from app.services.document_context import document_context, print_metadata
from app.services.goods_receipt_service import GoodsReceiptService

router = APIRouter(prefix="/goods-receipts", tags=["Goods Receipts"])


def receipt_actions(receipt: GoodsReceipt, user):
    receiving_role = has_any_role(user, "WAREHOUSE", "PURCHASING")
    return {"can_edit":False,"can_post":receipt.status=="DRAFT" and receiving_role,"can_return":receipt.status=="POSTED" and receiving_role,"can_print":True,"can_view_history":True,"can_manage_attachments":True}


def serialize_receipt(receipt: GoodsReceipt):
    purchase_order=receipt.purchase_order
    supplier=purchase_order.supplier if purchase_order else receipt.supplier
    return {
        "id":receipt.id,"receipt_number":receipt.receipt_number,"status":receipt.status,
        "purchase_order_id":receipt.purchase_order_id,"purchase_order_number":purchase_order.po_number if purchase_order else None,
        "source_mode":"PO" if purchase_order else "DIRECT","supplier_id":purchase_order.supplier_id if purchase_order else receipt.supplier_id,
        "supplier_name":supplier.name if supplier else None,"received_by_id":receipt.received_by_id,"received_by_name":receipt.received_by.full_name if receipt.received_by else None,
        "received_at":receipt.received_at,"source_type":receipt.source_type,"external_reference":receipt.external_reference,"delivery_note_number":receipt.external_reference,
        "receipt_type":receipt.receipt_type,"destination_type":receipt.destination_type,"warehouse_id":receipt.warehouse_id,"warehouse_name":receipt.warehouse.name if receipt.warehouse else None,
        "business_unit_id":receipt.business_unit_id,"location_id":receipt.location_id,"department_id":receipt.department_id,"notes":receipt.notes,
        "total_value":sum(Decimal(item.quantity)*Decimal(item.unit_cost) for item in receipt.items),
        "items":[{"id":item.id,"purchase_order_item_id":item.purchase_order_item_id,"product_id":item.product_id,"product_code":item.product.code if item.product else None,"product_name":item.product.name if item.product else None,"uom":(item.purchase_order_item.uom if item.purchase_order_item else None) or (item.product.uom if item.product else None),"quantity":item.quantity,"unit_cost":item.unit_cost,"line_total":Decimal(item.quantity)*Decimal(item.unit_cost)} for item in receipt.items],
    }


def remaining_items(purchase_order:PurchaseOrder):
    return [{"purchase_order_item_id":item.id,"product_id":item.product_id,"product_code":item.product.code if item.product else None,"product_name":item.product.name if item.product else None,"uom":item.uom or (item.product.uom if item.product else None),"ordered_quantity":item.quantity,"received_quantity":item.received_quantity,"remaining_quantity":Decimal(item.quantity)-Decimal(item.received_quantity or 0),"unit_cost":item.unit_price} for item in purchase_order.items if Decimal(item.quantity)>Decimal(item.received_quantity or 0)]


@router.get("")
def list_receipts(purchase_order_id:int|None=None,db:Session=Depends(get_db),_=Depends(get_current_user)):
    query=db.query(GoodsReceipt).options(selectinload(GoodsReceipt.purchase_order),selectinload(GoodsReceipt.supplier),selectinload(GoodsReceipt.items),selectinload(GoodsReceipt.received_by),selectinload(GoodsReceipt.warehouse))
    if purchase_order_id:query=query.filter(GoodsReceipt.purchase_order_id==purchase_order_id)
    return [serialize_receipt(item) for item in query.order_by(GoodsReceipt.id.desc()).all()]


@router.get("/receivable-purchase-orders")
def list_receivable_purchase_orders(db:Session=Depends(get_db),_=Depends(get_current_user)):
    orders=db.query(PurchaseOrder).filter(PurchaseOrder.status.in_({"APPROVED","PARTIALLY_RECEIVED"})).order_by(PurchaseOrder.id.desc()).all()
    return [{"id":order.id,"po_number":order.po_number,"supplier_id":order.supplier_id,"supplier_name":order.supplier.name if order.supplier else None,"status":order.status,"business_unit_id":order.business_unit_id,"department_id":order.department_id,"location_id":order.location_id,"items":remaining_items(order)} for order in orders if remaining_items(order)]


@router.get("/receivable-purchase-orders/{purchase_order_id}/items")
def get_remaining_purchase_order_items(purchase_order_id:int,db:Session=Depends(get_db),_=Depends(get_current_user)):
    order=db.get(PurchaseOrder,purchase_order_id)
    if not order:raise HTTPException(404,"Purchase order not found")
    if order.status not in {"APPROVED","PARTIALLY_RECEIVED"}:raise HTTPException(409,"Purchase order is not receivable")
    return remaining_items(order)


@router.post("",status_code=201)
def create_receipt(data:GoodsReceiptCreate,db:Session=Depends(get_db),user=Depends(get_current_user)):
    return serialize_receipt(GoodsReceiptService.create(db=db,data=data,user=user))


@router.get("/{receipt_id}")
def get_receipt(receipt_id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):
    receipt=db.get(GoodsReceipt,receipt_id)
    if not receipt:raise HTTPException(404,"Goods receipt not found")
    result=serialize_receipt(receipt);result.update(document_context(db,"GOODS_RECEIPT",receipt.id,receipt.status,user));result["allowed_actions"]=receipt_actions(receipt,user);return result


@router.post("/{receipt_id}/post")
def post_receipt(receipt_id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):
    return serialize_receipt(GoodsReceiptService.post(db=db,receipt_id=receipt_id,user=user))


@router.post("/{receipt_id}/return")
def return_receipt(receipt_id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):
    return serialize_receipt(GoodsReceiptService.return_receipt(db=db,receipt_id=receipt_id,user=user))


@router.get("/{receipt_id}/allowed-actions")
def get_allowed_actions(receipt_id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):
    receipt=db.get(GoodsReceipt,receipt_id)
    if not receipt:raise HTTPException(404,"Goods receipt not found")
    return receipt_actions(receipt,user)


@router.get("/{receipt_id}/print")
def print_receipt(receipt_id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):
    return {**get_receipt(receipt_id,db,user),"document_type":"Goods Receipt",**print_metadata(user)}
