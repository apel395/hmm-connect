from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import require_roles
from app.models.approval_request import ApprovalRequest
from app.models.purchase_order import PurchaseOrder
from app.models.department import Department
from app.models.location import Location
from app.models.product import Product
from app.models.supplier import Supplier
from app.schemas.approval import ApprovalDecisionRequest
from app.schemas.purchase_order import PurchaseOrderCreate
from app.services.purchase_order_service import PurchaseOrderService
from app.services.document_context import document_context, print_metadata


router = APIRouter(prefix="/purchase-orders", tags=["Purchase Orders"])
purchasing_user = require_roles("PURCHASING")

ACTIVE_STATUSES = {"DRAFT", "PENDING_APPROVAL", "APPROVED", "PARTIALLY_RECEIVED"}
HISTORY_STATUSES = {"RECEIVED", "CLOSED", "REJECTED", "CANCELLED", "EXPIRED"}


def approval_state(db: Session, purchase_order: PurchaseOrder):
    request = db.query(ApprovalRequest).filter(ApprovalRequest.entity_type == "PURCHASE_ORDER", ApprovalRequest.entity_id == purchase_order.id).first()
    if not request:
        return None, None
    current_step = next((step for step in request.steps if step.step_order == request.current_step_order), None)
    return request.status, current_step.approver_role_name if current_step else None


def approval_state_from_request(request: ApprovalRequest | None):
    if not request:
        return None, None
    current_step = next((step for step in request.steps if step.step_order == request.current_step_order), None)
    return request.status, current_step.approver_role_name if current_step else None


def _apply_tax(db: Session, purchase_order: PurchaseOrder, data: PurchaseOrderCreate) -> PurchaseOrder:
    if len(purchase_order.items) != len(data.items):
        raise HTTPException(status_code=500, detail="Purchase order item mapping changed while calculating PPN")
    subtotal = Decimal("0")
    tax_total = Decimal("0")
    for item, incoming in zip(purchase_order.items, data.items):
        source = item.purchase_requisition_item or item.market_list_item
        explicit_tax = "is_taxable" in incoming.model_fields_set or "tax_rate" in incoming.model_fields_set
        if source is not None and not explicit_tax:
            taxable = bool(source.is_taxable)
            rate = Decimal(source.tax_rate or 0) if taxable else Decimal("0")
        else:
            taxable = bool(incoming.is_taxable)
            rate = Decimal(incoming.tax_rate if taxable else 0)
        line_subtotal = Decimal(item.quantity) * Decimal(item.unit_price)
        tax = (line_subtotal * rate / Decimal("100")) if taxable else Decimal("0")
        item.is_taxable = taxable
        item.tax_rate = rate
        item.tax_amount = tax
        item.total_price = line_subtotal
        subtotal += line_subtotal
        tax_total += tax
    purchase_order.subtotal = subtotal
    purchase_order.tax_amount = tax_total
    purchase_order.total_amount = subtotal - Decimal(purchase_order.discount_amount or 0) + tax_total
    db.commit()
    db.refresh(purchase_order)
    return purchase_order


def _source_requisitions(purchase_order: PurchaseOrder):
    return purchase_order.source_purchase_requisitions


def _source_type(purchase_order: PurchaseOrder, requisitions) -> str:
    if requisitions:
        return "FROM_PR"
    if purchase_order.market_list_id:
        return "FROM_MARKET_LIST"
    return "DIRECT"


def serialize_purchase_order_summary(purchase_order: PurchaseOrder, approval_status=None, current_approver_role=None):
    requisitions = _source_requisitions(purchase_order)
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
        "purchase_requisition_ids": [item.id for item in requisitions],
        "source_pr_id": requisitions[0].id if requisitions else None,
        "source_pr_number": requisitions[0].pr_number if requisitions else None,
        "market_list_id": purchase_order.market_list_id,
        "source_market_list_number": purchase_order.market_list.ml_number if purchase_order.market_list else None,
        "creation_type": _source_type(purchase_order, requisitions),
        "status": purchase_order.status,
        "approval_status": approval_status,
        "current_approver_role": current_approver_role,
        "order_date": purchase_order.order_date,
        "expected_date": purchase_order.expected_date,
        "expiry_date": purchase_order.expiry_date,
        "total_amount": purchase_order.total_amount,
    }


def serialize_purchase_order(purchase_order: PurchaseOrder, approval_status=None, current_approver_role=None):
    requisitions = purchase_order.source_purchase_requisitions
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
        "source_purchase_requisitions": [{"id": item.id, "pr_number": item.pr_number} for item in requisitions],
        "source_pr_id": requisitions[0].id if requisitions else None,
        "source_pr_number": requisitions[0].pr_number if requisitions else None,
        "market_list_id": purchase_order.market_list_id,
        "source_market_list": {"id": purchase_order.market_list.id, "ml_number": purchase_order.market_list.ml_number} if purchase_order.market_list else None,
        "source_market_list_number": purchase_order.market_list.ml_number if purchase_order.market_list else None,
        "creation_type": _source_type(purchase_order, requisitions),
        "status": purchase_order.status,
        "approval_status": approval_status,
        "current_approver_role": current_approver_role,
        "order_date": purchase_order.order_date,
        "source_type": purchase_order.source_type,
        "external_reference": purchase_order.external_reference,
        "expected_date": purchase_order.expected_date,
        "expiry_date": purchase_order.expiry_date,
        "subtotal": purchase_order.subtotal,
        "discount_amount": purchase_order.discount_amount,
        "tax_amount": purchase_order.tax_amount,
        "total_amount": purchase_order.total_amount,
        "notes": purchase_order.notes,
        "created_at": purchase_order.created_at,
        "updated_at": purchase_order.updated_at,
        "items": [{
            "id": item.id,
            "purchase_requisition_item_id": item.purchase_requisition_item_id,
            "market_list_item_id": item.market_list_item_id,
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
            "is_taxable": item.is_taxable,
            "tax_rate": item.tax_rate,
            "tax_amount": item.tax_amount,
            "line_total": Decimal(item.total_price) + Decimal(item.tax_amount or 0),
        } for item in purchase_order.items],
    }


def purchase_order_result(db: Session, purchase_order: PurchaseOrder, user):
    result = serialize_purchase_order(purchase_order, *approval_state(db, purchase_order))
    result.update(document_context(db, "PURCHASE_ORDER", purchase_order.id, purchase_order.status, user))
    return result


@router.get("")
def list_purchase_orders(
    status: str | None = None,
    scope: str = Query(default="all", pattern="^(active|history|all)$"),
    search: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    base_query = db.query(PurchaseOrder).outerjoin(Supplier, Supplier.id == PurchaseOrder.supplier_id)
    if scope == "active":
        base_query = base_query.filter(PurchaseOrder.status.in_(ACTIVE_STATUSES))
    elif scope == "history":
        base_query = base_query.filter(PurchaseOrder.status.in_(HISTORY_STATUSES))
    if search and search.strip():
        term = f"%{search.strip()}%"
        base_query = base_query.filter(or_(PurchaseOrder.po_number.ilike(term), PurchaseOrder.external_reference.ilike(term), Supplier.name.ilike(term)))

    status_rows = base_query.with_entities(PurchaseOrder.status, func.count(PurchaseOrder.id)).group_by(PurchaseOrder.status).all()
    summary = {key: 0 for key in ["DRAFT", "PENDING_APPROVAL", "APPROVED", "PARTIALLY_RECEIVED", "RECEIVED", "REJECTED"]}
    summary.update({key: int(value) for key, value in status_rows})

    query = base_query
    if status:
        query = query.filter(PurchaseOrder.status == status.upper())
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
            selectinload(PurchaseOrder.market_list),
        )
        .order_by(PurchaseOrder.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    order_ids = [item.id for item in orders]
    approvals = (
        db.query(ApprovalRequest).options(selectinload(ApprovalRequest.steps)).filter(ApprovalRequest.entity_type == "PURCHASE_ORDER", ApprovalRequest.entity_id.in_(order_ids)).all()
        if order_ids else []
    )
    approval_map = {item.entity_id: item for item in approvals}
    return {
        "items": [serialize_purchase_order_summary(item, *approval_state_from_request(approval_map.get(item.id))) for item in orders],
        "page": page,
        "page_size": page_size,
        "total_items": total_items,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_previous": page > 1,
        "summary": summary,
    }


@router.get("/form-options")
def purchase_order_form_options(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return {
        "departments": [{"id": row.id, "code": row.code, "name": row.name} for row in db.query(Department).filter(Department.is_active.is_(True)).order_by(Department.name)],
        "locations": [{"id": row.id, "code": row.code, "name": row.name} for row in db.query(Location).filter(Location.is_active.is_(True)).order_by(Location.name)],
        "products": [{"id": row.id, "code": row.code, "name": row.name, "description": row.description, "uom": row.uom} for row in db.query(Product).filter(Product.is_active.is_(True)).order_by(Product.name)],
    }


@router.post("", status_code=201)
def create_purchase_order(data: PurchaseOrderCreate, db: Session = Depends(get_db), user=Depends(purchasing_user)):
    purchase_order = PurchaseOrderService.create(db=db, data=data, user=user)
    purchase_order = _apply_tax(db, purchase_order, data)
    return purchase_order_result(db, purchase_order, user)


@router.put("/{purchase_order_id}")
@router.patch("/{purchase_order_id}")
def update_purchase_order(purchase_order_id: int, data: PurchaseOrderCreate, db: Session = Depends(get_db), user=Depends(purchasing_user)):
    purchase_order = PurchaseOrderService.update(db=db, purchase_order_id=purchase_order_id, data=data, user=user)
    purchase_order = _apply_tax(db, purchase_order, data)
    return purchase_order_result(db, purchase_order, user)


@router.get("/{purchase_order_id}")
def get_purchase_order(purchase_order_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    purchase_order = db.get(PurchaseOrder, purchase_order_id)
    if not purchase_order:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    return purchase_order_result(db, purchase_order, user)


@router.get("/{purchase_order_id}/print")
def print_purchase_order(purchase_order_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return {**get_purchase_order(purchase_order_id, db, user), "document_type": "Purchase Order", **print_metadata(user)}


@router.post("/{purchase_order_id}/reopen")
def reopen_purchase_order(purchase_order_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return purchase_order_result(db, PurchaseOrderService.reopen(db=db, purchase_order_id=purchase_order_id, user=user), user)


@router.post("/{purchase_order_id}/submit")
def submit_purchase_order(purchase_order_id: int, db: Session = Depends(get_db), user=Depends(purchasing_user)):
    return purchase_order_result(db, PurchaseOrderService.submit(db=db, purchase_order_id=purchase_order_id, user=user), user)


@router.post("/{purchase_order_id}/approve")
def approve_purchase_order(purchase_order_id: int, data: ApprovalDecisionRequest | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return purchase_order_result(db, PurchaseOrderService.approve(db=db, purchase_order_id=purchase_order_id, data=data, user=user), user)


@router.post("/{purchase_order_id}/reject")
def reject_purchase_order(purchase_order_id: int, data: ApprovalDecisionRequest | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return purchase_order_result(db, PurchaseOrderService.reject(db=db, purchase_order_id=purchase_order_id, data=data, user=user), user)


@router.post("/{purchase_order_id}/cancel")
def cancel_purchase_order(purchase_order_id: int, db: Session = Depends(get_db), user=Depends(purchasing_user)):
    return purchase_order_result(db, PurchaseOrderService.cancel(db=db, purchase_order_id=purchase_order_id, user=user), user)