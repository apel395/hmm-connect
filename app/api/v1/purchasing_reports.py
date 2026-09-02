from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
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
from app.services.location_access import apply_location_scope

router = APIRouter(prefix="/purchasing", tags=["Purchasing Reports"])

MONEY = Decimal("0.01")


def _round(value) -> Decimal:
    return Decimal(value or 0).quantize(MONEY)


@router.get("/summary")
def purchasing_summary(
    date_from: date | None = None,
    date_to: date | None = None,
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
    ).scalar_one()
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
    ).scalar_one()

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