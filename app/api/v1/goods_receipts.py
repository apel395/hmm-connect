from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.goods_receipt import GoodsReceipt
from app.schemas.goods_receipt import GoodsReceiptCreate
from app.services.goods_receipt_service import GoodsReceiptService


router = APIRouter(prefix="/goods-receipts", tags=["Goods Receipts"])


def serialize_receipt(receipt: GoodsReceipt):
    return {
        "id": receipt.id,
        "receipt_number": receipt.receipt_number,
        "purchase_order_id": receipt.purchase_order_id,
        "purchase_order_number": receipt.purchase_order.po_number,
        "received_by_id": receipt.received_by_id,
        "received_by_name": receipt.received_by.full_name if receipt.received_by else None,
        "received_at": receipt.received_at,
        "source_type": receipt.source_type,
        "external_reference": receipt.external_reference,
        "receipt_type": receipt.receipt_type,
        "destination_type": receipt.destination_type,
        "warehouse_id": receipt.warehouse_id,
        "warehouse_name": receipt.warehouse.name if receipt.warehouse else None,
        "notes": receipt.notes,
        "items": [
            {
                "id": item.id,
                "purchase_order_item_id": item.purchase_order_item_id,
                "product_id": item.product_id,
                "product_code": item.product.code,
                "product_name": item.product.name,
                "quantity": item.quantity,
                "unit_cost": item.unit_cost,
            }
            for item in receipt.items
        ],
    }


@router.get("")
def list_receipts(
    purchase_order_id: int | None = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    query = db.query(GoodsReceipt)
    if purchase_order_id:
        query = query.filter(GoodsReceipt.purchase_order_id == purchase_order_id)
    return [
        serialize_receipt(item)
        for item in query.order_by(GoodsReceipt.id.desc()).all()
    ]


@router.get("/{receipt_id}")
def get_receipt(
    receipt_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    receipt = db.get(GoodsReceipt, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Goods receipt not found")
    return serialize_receipt(receipt)


@router.post("", status_code=201)
def receive_goods(
    data: GoodsReceiptCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    role_names = {role.name for role in user.roles}
    if not role_names.intersection({"WAREHOUSE", "ADMIN"}):
        raise HTTPException(status_code=403, detail="Warehouse access required")
    receipt = GoodsReceiptService.receive(db=db, data=data, user=user)
    return serialize_receipt(receipt)
