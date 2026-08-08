from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import require_roles
from app.models.approval_request import ApprovalRequest
from app.models.purchase_order import PurchaseOrder
from app.models.department import Department
from app.models.location import Location
from app.models.product import Product
from app.schemas.approval import ApprovalDecisionRequest
from app.schemas.purchase_order import PurchaseOrderCreate
from app.services.purchase_order_service import PurchaseOrderService
from app.services.document_context import document_context, print_metadata


router = APIRouter(prefix="/purchase-orders", tags=["Purchase Orders"])
purchasing_user = require_roles("PURCHASING")

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
        "supplier_name": purchase_order.supplier.name if purchase_order.supplier else None,
        "business_unit_id": purchase_order.business_unit_id,
        "business_unit_name": purchase_order.business_unit.name if purchase_order.business_unit else None,
        "department_id": purchase_order.department_id,
        "department_name": purchase_order.department.name if purchase_order.department else None,
        "location_id": purchase_order.location_id,
        "location_name": purchase_order.location.name if purchase_order.location else None,
        "purchase_requisition_ids": purchase_order.purchase_requisition_ids,
        "source_purchase_requisitions": [
            {"id": item.id, "pr_number": item.pr_number}
            for item in purchase_order.source_purchase_requisitions
        ],
        "source_pr_id": (
            purchase_order.source_purchase_requisitions[0].id
            if purchase_order.source_purchase_requisitions else None
        ),
        "source_pr_number": (
            purchase_order.source_purchase_requisitions[0].pr_number
            if purchase_order.source_purchase_requisitions else None
        ),
        "creation_type": "FROM_PR" if purchase_order.purchase_requisition_ids else "DIRECT",
        "status": purchase_order.status,
        "approval_status": approval_status,
        "current_approver_role": current_approver_role,
        "order_date": purchase_order.order_date,
        "source_type": purchase_order.source_type,
        "external_reference": purchase_order.external_reference,
        "expected_date": purchase_order.expected_date,
        "expiry_date": purchase_order.expiry_date,
        "total_amount": purchase_order.total_amount,
        "notes": purchase_order.notes,
        "created_at": purchase_order.created_at,
        "updated_at": purchase_order.updated_at,
        "items": [
            {
                "id": item.id,
                "purchase_requisition_item_id": item.purchase_requisition_item_id,
                "product_id": item.product_id,
                "product_code": item.product.code if item.product else None,
                "product_name": item.product.name if item.product else None,
                "description": item.description if item.description is not None else (item.product.description if item.product else None),
                "uom": item.uom or (item.product.uom if item.product else None),
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
    scope: str = Query(default="all", pattern="^(active|history|all)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
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
    total_items = query.count()
    total_pages = (total_items + page_size - 1) // page_size
    orders = (
        query.options(
            selectinload(PurchaseOrder.supplier),
            selectinload(PurchaseOrder.business_unit),
            selectinload(PurchaseOrder.department),
            selectinload(PurchaseOrder.location),
            selectinload(PurchaseOrder.purchase_requisitions),
            selectinload(PurchaseOrder.purchase_requisition),
            selectinload(PurchaseOrder.items),
        )
        .order_by(PurchaseOrder.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [
        serialize_purchase_order(
            item,
            *approval_state(db, item),
        )
        for item in orders
    ]
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total_items": total_items,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_previous": page > 1,
    }


@router.get("/form-options")
def purchase_order_form_options(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return {
        "departments": [{"id": row.id, "code": row.code, "name": row.name} for row in db.query(Department).filter(Department.is_active.is_(True)).order_by(Department.name)],
        "locations": [{"id": row.id, "code": row.code, "name": row.name} for row in db.query(Location).filter(Location.is_active.is_(True)).order_by(Location.name)],
        "products": [{"id": row.id, "code": row.code, "name": row.name, "description": row.description, "uom": row.uom} for row in db.query(Product).filter(Product.is_active.is_(True)).order_by(Product.name)],
    }


@router.post("", status_code=201)
def create_purchase_order(
    data: PurchaseOrderCreate,
    db: Session = Depends(get_db),
    user=Depends(purchasing_user),
):
    purchase_order = PurchaseOrderService.create(db=db, data=data, user=user)
    return serialize_purchase_order(
        purchase_order,
        *approval_state(db, purchase_order),
    )


@router.put("/{purchase_order_id}")
@router.patch("/{purchase_order_id}")
def update_purchase_order(purchase_order_id: int, data: PurchaseOrderCreate,
                          db: Session = Depends(get_db), user=Depends(purchasing_user)):
    purchase_order = PurchaseOrderService.update(db=db, purchase_order_id=purchase_order_id, data=data, user=user)
    result = serialize_purchase_order(purchase_order, *approval_state(db, purchase_order))
    result.update(document_context(db, "PURCHASE_ORDER", purchase_order.id, purchase_order.status, user))
    return result


@router.get("/{purchase_order_id}")
def get_purchase_order(
    purchase_order_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    purchase_order = db.get(PurchaseOrder, purchase_order_id)
    if not purchase_order:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    result = serialize_purchase_order(
        purchase_order,
        *approval_state(db, purchase_order),
    )
    result.update(document_context(db, "PURCHASE_ORDER", purchase_order.id, purchase_order.status, user))
    return result


@router.get("/{purchase_order_id}/print")
def print_purchase_order(purchase_order_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    result = get_purchase_order(purchase_order_id, db, user)
    return {**result, "document_type": "Purchase Order", **print_metadata(user)}


@router.post("/{purchase_order_id}/submit")
def submit_purchase_order(
    purchase_order_id: int,
    db: Session = Depends(get_db),
    user=Depends(purchasing_user),
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
    user=Depends(purchasing_user),
):
    purchase_order = PurchaseOrderService.cancel(
        db=db, purchase_order_id=purchase_order_id, user=user
    )
    return serialize_purchase_order(
        purchase_order,
        *approval_state(db, purchase_order),
    )
