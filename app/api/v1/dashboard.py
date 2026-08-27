from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_permission
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_requisition import PurchaseRequisition
from app.services.ap_metrics import ap_metrics
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
    if not has_permission(user, "finance.view"):
        raise HTTPException(403, "Finance dashboard access required")
    end = date_to or as_of_date or date.today()
    start = date_from or end.replace(day=1)
    effective_as_of = as_of_date or end
    try:
        result = FinanceDashboardService(db, user).build(
            as_of_date=effective_as_of,
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

    # Keep Finance Dashboard AP cards and forecasts on the exact same liability
    # definition as Accounts Payable / Aging: verified or posted invoices with
    # a positive authoritative balance after payments and adjustments.
    synced_ap, _ = ap_metrics(
        db,
        as_of_date=effective_as_of,
        business_unit_id=business_unit_id,
        location_id=location_id,
        department_id=department_id,
    )
    result["accounts_payable"] = synced_ap
    forecast = result.get("forecast") or {}
    current_cash = Decimal(forecast.get("current_cash") or result.get("cash_position", {}).get("total_liquid_cash") or 0)
    due7 = synced_ap["overdue_ap"] + synced_ap["due_today"] + synced_ap["due_next_7_days"]
    due30 = due7 + synced_ap["due_next_30_days"]
    forecast["overdue_payables"] = synced_ap["overdue_ap"]
    forecast["payables_due_7_days"] = due7
    forecast["payables_due_30_days"] = due30
    forecast["forecast_after_due_7_days"] = current_cash - due7
    forecast["forecast_after_due_30_days"] = current_cash - due30
    forecast["forecast_after_all_outstanding_ap"] = current_cash - synced_ap["total_outstanding_ap"]
    po_commitments = Decimal(forecast.get("approved_po_commitments") or 0)
    forecast["forecast_after_ap_and_po_commitments"] = current_cash - synced_ap["total_outstanding_ap"] - po_commitments
    result["forecast"] = forecast

    return serialize(result)
