from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.api.v1.purchase_orders import ACTIVE_STATUSES
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_permission
from app.models.goods_receipt import GoodsReceipt
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_requisition import PurchaseRequisition
from app.models.supplier import Supplier
from app.models.user import User
from app.services.organization_access import resolve_organization_access, effective_business_unit
from app.services.location_access import apply_location_scope
from app.services.purchasing_insights_service import PurchasingInsightsService

router = APIRouter(prefix="/purchasing", tags=["Purchasing Reports"])

MONEY = Decimal("0.01")


def _round(value) -> Decimal:
    return Decimal(value or 0).quantize(MONEY)


@router.get("/summary")
def purchasing_summary(
    date_from: date | None = None,
    date_to: date | None = None,
    business_unit_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not has_permission(user, "reports.purchasing"):
        return {
            "allowed": False,
            "detail": "reports.purchasing permission required",
        }

    pr_query = apply_location_scope(db.query(PurchaseRequisition), PurchaseRequisition.location_id, user)
    po_query = apply_location_scope(db.query(PurchaseOrder), PurchaseOrder.location_id, user)
    gr_query = apply_location_scope(db.query(GoodsReceipt), GoodsReceipt.location_id, user)

    scope=resolve_organization_access(db,user,business_unit_id=business_unit_id)
    for model,name in ((PurchaseRequisition,"pr"),(PurchaseOrder,"po"),(GoodsReceipt,"gr")):
        query={"pr":pr_query,"po":po_query,"gr":gr_query}[name]
        for dimension,value in scope.items():
            if value is not None:
                column=effective_business_unit(model.business_unit_id,model.location_id) if dimension=="business_unit_id" else getattr(model,dimension)
                query=query.filter(column==value)
        if name=="pr":pr_query=query
        elif name=="po":po_query=query
        else:gr_query=query
    if date_from:
        pr_query = pr_query.filter(PurchaseRequisition.request_date >= date_from)
        po_query = po_query.filter(PurchaseOrder.order_date >= date_from)
        gr_query = gr_query.filter(GoodsReceipt.received_at >= date_from)
    if date_to:
        pr_query = pr_query.filter(PurchaseRequisition.request_date <= date_to)
        po_query = po_query.filter(PurchaseOrder.order_date <= date_to)
        gr_query = gr_query.filter(GoodsReceipt.received_at <= date_to)

    pr_status = dict(
        pr_query.with_entities(PurchaseRequisition.status, func.count(PurchaseRequisition.id))
        .group_by(PurchaseRequisition.status)
        .all()
    )
    pr_total = sum(pr_status.values())

    po_status = dict(
        po_query.with_entities(PurchaseOrder.status, func.count(PurchaseOrder.id))
        .group_by(PurchaseOrder.status)
        .all()
    )
    po_total = sum(po_status.values())

    committed_value = po_query.with_entities(
        func.coalesce(
            func.sum(
                case(
                    (PurchaseOrder.status.notin_({"VOID", "CANCELLED", "REJECTED", "EXPIRED"}), PurchaseOrder.subtotal),
                    else_=0,
                )
            ),
            0,
        )
    ).scalar()
    open_po = po_query.filter(
        PurchaseOrder.status.in_({"APPROVED", "PARTIALLY_RECEIVED"})
    ).with_entities(
        func.count(PurchaseOrder.id),
        func.coalesce(func.sum(func.coalesce(PurchaseOrder.subtotal, 0)), 0),
    ).one()
    open_count, open_value = int(open_po[0] or 0), _round(open_po[1])

    gr_status = dict(
        gr_query.with_entities(GoodsReceipt.status, func.count(GoodsReceipt.id))
        .group_by(GoodsReceipt.status)
        .all()
    )
    gr_total = sum(gr_status.values())
    received_value = gr_query.filter(GoodsReceipt.status == "POSTED").with_entities(
        func.coalesce(func.sum(func.coalesce(GoodsReceipt.subtotal, 0)), 0)
    ).scalar()

    supplier_rows = (
        gr_query.filter(GoodsReceipt.status == "POSTED")
        .join(Supplier, Supplier.id == GoodsReceipt.supplier_id)
        .with_entities(
            Supplier.id,
            Supplier.name,
            func.count(GoodsReceipt.id),
            func.coalesce(func.sum(func.coalesce(GoodsReceipt.subtotal, 0)), 0),
        )
        .group_by(Supplier.id, Supplier.name)
        .order_by(func.sum(func.coalesce(GoodsReceipt.subtotal, 0)).desc())
        .limit(5)
        .all()
    )
    top_suppliers = [
        {
            "supplier_id": supplier_id,
            "supplier_name": supplier_name,
            "receipt_count": int(count or 0),
            "received_value": _round(value),
        }
        for supplier_id, supplier_name, count, value in supplier_rows
    ]

    return {
        "allowed": True,
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "requisitions": {
            "total": pr_total,
            "status_counts": {key: int(value) for key, value in pr_status.items()},
        },
        "purchase_orders": {
            "total": po_total,
            "status_counts": {key: int(value) for key, value in po_status.items()},
            "committed_value": _round(committed_value),
            "open_count": open_count,
            "open_value": open_value,
        },
        "receipts": {
            "total": gr_total,
            "status_counts": {key: int(value) for key, value in gr_status.items()},
            "posted_value": _round(received_value),
        },
        "top_suppliers": top_suppliers,
    }


@router.get("/price-history")
def price_history(
    business_unit_id: int | None = None,
    product_id: int | None = None,
    supplier_id: int | None = None,
    search: str | None = Query(default=None, max_length=100),
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not has_permission(user, "reports.purchasing"):
        raise HTTPException(403, "Purchasing report access required")
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "From date must not exceed To date")
    return PurchasingInsightsService(db, user).price_history(
        product_id=product_id, supplier_id=supplier_id, search=search,
        date_from=date_from, date_to=date_to, page=page, page_size=page_size,business_unit_id=business_unit_id,
    )


@router.get("/top")
def top_purchases(
    year: int = Query(..., ge=2026, le=2100),
    month: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not has_permission(user, "reports.purchasing"):
        raise HTTPException(403, "Purchasing report access required")
    return PurchasingInsightsService(db, user).rankings(year=year, month=month, limit=10)
