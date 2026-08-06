from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_requisition import PurchaseRequisition
from app.services.finance_dashboard_service import FinanceDashboardService


router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def serialize(value):
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if isinstance(value, (date,)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: serialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [serialize(item) for item in value]
    return value


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


@router.get("/finance")
def finance_dashboard(
    as_of_date: date | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    location_id: int | None = None,
    department_id: int | None = None,
    business_unit_id: int | None = None,
    cash_account_id: int | None = None,
    currency: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if not {role.name for role in user.roles}.intersection({"FINANCE", "ADMIN"}):
        raise HTTPException(403, "Finance dashboard access required")
    end = date_to or as_of_date or date.today()
    start = date_from or end.replace(day=1)
    try:
        result = FinanceDashboardService(db, user).build(
            as_of_date=as_of_date or end,
            date_from=start,
            date_to=end,
            location_id=location_id,
            department_id=department_id,
            business_unit_id=business_unit_id,
            cash_account_id=cash_account_id,
            currency=currency,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return serialize(result)
