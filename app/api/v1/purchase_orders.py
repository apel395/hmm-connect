from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.purchase_order import PurchaseOrder


router = APIRouter(prefix="/purchase-orders", tags=["Purchase Orders"])


@router.get("")
def list_purchase_orders(
    status: str | None = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    query = db.query(PurchaseOrder)
    if status:
        query = query.filter(PurchaseOrder.status == status)
    return query.order_by(PurchaseOrder.id.desc()).all()


@router.get("/{purchase_order_id}")
def get_purchase_order(
    purchase_order_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    purchase_order = db.get(PurchaseOrder, purchase_order_id)
    if not purchase_order:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    return purchase_order
