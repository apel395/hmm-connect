from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.approval_request import ApprovalRequest
from app.models.purchase_order import PurchaseOrder
from app.schemas.approval import ApprovalDecisionRequest
from app.schemas.purchase_order import PurchaseOrderCreate
from app.services.purchase_order_service import PurchaseOrderService


router = APIRouter(prefix="/purchase-orders", tags=["Purchase Orders"])

ACTIVE_STATUSES = {"DRAFT", "PENDING_APPROVAL", "APPROVED", "PARTIALLY_RECEIVED"}
HISTORY_STATUSES = {"RECEIVED", "CLOSED", "REJECTED", "CANCELLED", "EXPIRED"}


def approval_state(db: Session, purchase_order: PurchaseOrder):
    request = (
        db.query(ApprovalRequest)
        .filter(
            ApprovalRequest.entity_type == "PURCHASE_ORDER",
            ApprovalRequest.entity_id == purchase_order.id,
        )
        .first()
    )
    if not request:
        return None, None
    current_step = next(
        (
            step
            for step in request.steps
            if step.step_order == request.current_step_order
        ),
        None,
    )
    return (
        request.status,
        current_step.approver_role_name if current_step else None,
    )


def serialize_purchase_order(
    purchase_order: PurchaseOrder,
    approval_status=None,
    current_approver_role=None,
):
    return {
        "id": purchase_order.id,
        "po_number": purchase_order.po_number,
        "supplier_id": purchase_order.supplier_id,
        "supplier_name": purchase_order.supplier.name,
        "purchase_requisition_ids": purchase_order.purchase_requisition_ids,
        "status": purchase_order.status,
        "approval_status": approval_status,
        "current_approver_role": current_approver_role,
        "order_date": purchase_order.order_date,
        "expected_date": purchase_order.expected_date,
        "expiry_date": purchase_order.expiry_date,
        "receipt_tolerance_percent": purchase_order.receipt_tolerance_percent,
        "total_amount": purchase_order.total_amount,
        "notes": purchase_order.notes,
        "created_at": purchase_order.created_at,
        "updated_at": purchase_order.updated_at,
        "items": [
            {
                "id": item.id,
                "purchase_requisition_item_id": item.purchase_requisition_item_id,
                "product_id": item.product_id,
                "product_code": item.product.code,
                "product_name": item.product.name,
                "uom": item.product.uom,
                "quantity": item.quantity,
                "received_quantity": item.received_quantity,
                "remaining_quantity": item.quantity - item.received_quantity,
                "unit_price": item.unit_price,
                "total_price": item.total_price,
            }
            for item in purchase_order.items
        ],
    }


@router.get("")
def list_purchase_orders(
    status: str | None = None,
    scope: str = Query(default="active", pattern="^(active|history|all)$"),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    query = db.query(PurchaseOrder)
    if status:
        query = query.filter(PurchaseOrder.status == status.upper())
    elif scope == "active":
        query = query.filter(PurchaseOrder.status.in_(ACTIVE_STATUSES))
    elif scope == "history":
        query = query.filter(PurchaseOrder.status.in_(HISTORY_STATUSES))
    return [
        serialize_purchase_order(
            item,
            *approval_state(db, item),
        )
        for item in query.order_by(PurchaseOrder.id.desc()).all()
    ]


@router.post("", status_code=201)
def create_purchase_order(
    data: PurchaseOrderCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    purchase_order = PurchaseOrderService.create(db=db, data=data, user=user)
    return serialize_purchase_order(
        purchase_order,
        *approval_state(db, purchase_order),
    )


@router.get("/{purchase_order_id}")
def get_purchase_order(
    purchase_order_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    purchase_order = db.get(PurchaseOrder, purchase_order_id)
    if not purchase_order:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    return serialize_purchase_order(
        purchase_order,
        *approval_state(db, purchase_order),
    )


@router.post("/{purchase_order_id}/submit")
def submit_purchase_order(
    purchase_order_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    purchase_order = PurchaseOrderService.submit(
        db=db, purchase_order_id=purchase_order_id, user=user
    )
    return serialize_purchase_order(
        purchase_order,
        *approval_state(db, purchase_order),
    )


@router.post("/{purchase_order_id}/approve")
def approve_purchase_order(
    purchase_order_id: int,
    data: ApprovalDecisionRequest | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    purchase_order = PurchaseOrderService.approve(
        db=db, purchase_order_id=purchase_order_id, data=data, user=user
    )
    return serialize_purchase_order(
        purchase_order,
        *approval_state(db, purchase_order),
    )


@router.post("/{purchase_order_id}/reject")
def reject_purchase_order(
    purchase_order_id: int,
    data: ApprovalDecisionRequest | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    purchase_order = PurchaseOrderService.reject(
        db=db, purchase_order_id=purchase_order_id, data=data, user=user
    )
    return serialize_purchase_order(
        purchase_order,
        *approval_state(db, purchase_order),
    )


@router.post("/{purchase_order_id}/cancel")
def cancel_purchase_order(
    purchase_order_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    purchase_order = PurchaseOrderService.cancel(
        db=db, purchase_order_id=purchase_order_id, user=user
    )
    return serialize_purchase_order(
        purchase_order,
        *approval_state(db, purchase_order),
    )