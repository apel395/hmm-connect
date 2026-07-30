from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_requisition import PurchaseRequisition


router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary")
def summary(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return {
        "pending_purchase_requisitions": db.query(PurchaseRequisition)
        .filter(PurchaseRequisition.status == "PENDING_APPROVAL")
        .count(),
        "pending_purchase_orders": db.query(PurchaseOrder)
        .filter(PurchaseOrder.status.in_(["DRAFT", "PENDING_APPROVAL", "APPROVED"]))
        .count(),
        "inventory_items": db.query(Inventory).count(),
        "active_products": db.query(Product)
        .filter(Product.is_active.is_(True))
        .count(),
        "inventory_value": db.query(
            func.coalesce(func.sum(Inventory.quantity * Inventory.average_cost), 0)
        ).scalar(),
    }
