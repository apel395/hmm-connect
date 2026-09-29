from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_permission
from app.models.approval_request import ApprovalRequest
from app.models.chart_of_account import ChartOfAccount
from app.models.goods_receipt import GoodsReceipt
from app.models.inventory import Inventory
from app.models.location import Location
from app.models.warehouse import Warehouse
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_requisition import PurchaseRequisition
from app.services.ap_metrics import ap_metrics
from app.services.finance_dashboard_service import FinanceDashboardService
from app.services.location_access import apply_location_scope, apply_warehouse_scope, assigned_location_id, resolve_location_id


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
    location_id = resolve_location_id(user, location_id)
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



@router.get("/overview")
def overview(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Permission-aware, location-scoped global dashboard from full data sets."""
    location_id = assigned_location_id(user)
    location = db.get(Location, location_id) if location_id else None
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": {"location_id": location_id, "location_name": location.name if location else None},
        "purchasing": {},
        "inventory": None,
        "finance": None,
    }
    purchasing = result["purchasing"]

    if has_permission(user, "pr.view"):
        requisitions = apply_location_scope(db.query(PurchaseRequisition), PurchaseRequisition.location_id, user)
        purchasing["pr_waiting"] = requisitions.filter(PurchaseRequisition.status == "PENDING_APPROVAL").count()
        purchasing["pr_draft"] = requisitions.filter(PurchaseRequisition.status == "DRAFT").count()

    if has_permission(user, "po.view"):
        orders = apply_location_scope(db.query(PurchaseOrder), PurchaseOrder.location_id, user)
        purchasing["po_waiting"] = orders.filter(PurchaseOrder.status == "PENDING_APPROVAL").count()
        purchasing["po_open"] = orders.filter(PurchaseOrder.status.in_(("APPROVED", "PARTIALLY_RECEIVED"))).count()
        recent = orders.order_by(PurchaseOrder.order_date.desc(), PurchaseOrder.id.desc()).limit(5).all()
        purchasing["recent_orders"] = [
            {
                "id": po.id, "po_number": po.po_number, "supplier_name": po.supplier.name if po.supplier else None,
                "order_date": po.order_date, "status": po.status, "total_amount": po.total_amount,
                "currency": po.currency,
            }
            for po in recent
        ]

    if has_permission(user, "receiving.view"):
        receipts = apply_location_scope(db.query(GoodsReceipt), GoodsReceipt.location_id, user)
        approvals = (
            db.query(ApprovalRequest.entity_id, ApprovalRequest.status)
            .filter(ApprovalRequest.entity_type == "GOODS_RECEIPT")
            .subquery()
        )
        receiving = receipts.outerjoin(approvals, approvals.c.entity_id == GoodsReceipt.id)
        purchasing["rr_waiting"] = receiving.filter(
            GoodsReceipt.status == "DRAFT", approvals.c.status == "PENDING"
        ).count()
        purchasing["rr_ready"] = receiving.filter(
            GoodsReceipt.status == "DRAFT", approvals.c.status == "APPROVED"
        ).count()

    if has_permission(user, "inventory.view"):
        stock = (
            db.query(Inventory, Product, Warehouse)
            .join(Product, Product.id == Inventory.product_id)
            .join(Warehouse, Warehouse.id == Inventory.warehouse_id)
            .filter(Product.is_active.is_(True), Warehouse.is_active.is_(True))
        )
        stock = apply_warehouse_scope(stock, user)
        low = stock.filter(
            Product.minimum_stock > 0,
            Inventory.quantity <= Product.minimum_stock,
        )
        stock_value = stock.with_entities(
            func.count(Inventory.id),
            func.coalesce(func.sum(Inventory.quantity * Inventory.average_cost), 0),
        ).one()
        account_rows = (
            stock.outerjoin(ChartOfAccount, ChartOfAccount.id == Product.inventory_account_id)
            .with_entities(
                ChartOfAccount.id, ChartOfAccount.account_number, ChartOfAccount.account_name,
                func.coalesce(func.sum(Inventory.quantity * Inventory.average_cost), 0),
            )
            .group_by(ChartOfAccount.id, ChartOfAccount.account_number, ChartOfAccount.account_name)
            .order_by(ChartOfAccount.account_number)
            .all()
        )
        top_low = low.order_by(
            (Product.minimum_stock - Inventory.quantity).desc(), Product.name, Warehouse.name
        ).limit(5).all()
        result["inventory"] = {
            "stock_lines": stock_value[0],
            "stock_value": stock_value[1],
            "reorder_required": low.count(),
            "by_account": [
                {"account_id": account_id, "account_code": code, "account_name": name, "stock_value": value}
                for account_id, code, name, value in account_rows
            ],
            "low_stock": [
                {
                    "id": item.id, "product_code": product.code, "product_name": product.name,
                    "warehouse_name": warehouse.name, "quantity": item.quantity,
                    "minimum_stock": product.minimum_stock,
                    "shortage": product.minimum_stock - item.quantity,
                    "uom": product.uom,
                }
                for item, product, warehouse in top_low
            ],
        }

    if has_permission(user, "finance.view"):
        payable, _ = ap_metrics(db, as_of_date=date.today(), location_id=location_id)
        result["finance"] = {
            "ap_outstanding": payable["total_outstanding_ap"],
            "ap_overdue": payable["overdue_ap"],
            "overdue_invoice_count": payable["overdue_invoice_count"],
        }
    return serialize(result)
