from app.services.document_print_tracking import print_context
from datetime import date
from decimal import Decimal
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import is_superuser, require_permission
from app.models.business_unit import BusinessUnit
from app.models.department import Department
from app.models.location import Location
from app.models.location_department import LocationDepartment
from app.models.purchase_requisition import PurchaseRequisition
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.user import User
from app.schemas.approval import ApprovalDecisionRequest
from app.schemas.purchase_requisition import PurchaseRequisitionConvertCreate, PurchaseRequisitionCreate
from app.services.activity_service import AuditService
from app.services.approval import reset_approval
from app.services.purchase_requisition_service import PurchaseRequisitionService
from app.services.document_context import document_context, print_metadata
from app.services.location_access import apply_location_scope, require_location_access, resolve_location_id


router = APIRouter(prefix="/purchase-requisitions", tags=["Purchase Requisitions"])
pr_view_user = require_permission("pr.view")
pr_create_user = require_permission("pr.create")
pr_edit_user = require_permission("pr.edit")
pr_submit_user = require_permission("pr.submit")
pr_approve_user = require_permission("pr.approve")
pr_convert_user = require_permission("pr.convert")

ACTIVE_STATUSES = {"DRAFT", "PENDING_APPROVAL", "APPROVED", "PARTIALLY_CONVERTED"}
HISTORY_STATUSES = {"CONVERTED", "REJECTED", "CANCELLED", "EXPIRED"}


def _organization_context(db: Session, requisition: PurchaseRequisition) -> dict:
    business_unit = db.get(BusinessUnit, requisition.business_unit_id) if requisition.business_unit_id else None
    department = db.get(Department, requisition.department_id) if requisition.department_id else None
    location = db.get(Location, requisition.location_id) if requisition.location_id else None
    return {
        "business_unit_id": requisition.business_unit_id,
        "business_unit_name": business_unit.name if business_unit else None,
        "department_id": requisition.department_id,
        "department_name": department.name if department else None,
        "location_id": requisition.location_id,
        "location_name": location.name if location else None,
    }


def _apply_scope(query, scope: str):
    query = query.filter(PurchaseRequisition.status != "ARCHIVED")
    if scope == "active":
        return query.filter(PurchaseRequisition.status.in_(ACTIVE_STATUSES))
    if scope == "history":
        return query.filter(PurchaseRequisition.status.in_(HISTORY_STATUSES))
    return query


def _list_row(db: Session, requisition: PurchaseRequisition, requester_name: str | None = None) -> dict:
    return {
        "id": requisition.id,
        "pr_number": requisition.pr_number,
        "status": requisition.status,
        "request_date": requisition.request_date,
        "expiry_date": requisition.expiry_date,
        "requester_name": requester_name,
        "subtotal": requisition.subtotal,
        "tax_amount": requisition.tax_amount,
        "total_amount": requisition.total_amount,
        "source_type": requisition.source_type,
        "external_reference": requisition.external_reference,
        **_organization_context(db, requisition),
    }


def _apply_tax(db: Session, requisition: PurchaseRequisition, data: PurchaseRequisitionCreate) -> PurchaseRequisition:
    if len(requisition.items) != len(data.items):
        raise HTTPException(status_code=500, detail="Purchase requisition item mapping changed while calculating PPN")
    subtotal = Decimal("0")
    tax_total = Decimal("0")
    for item in requisition.items:
        line_subtotal = Decimal(item.quantity) * Decimal(item.estimated_price)
        taxable = bool(item.is_taxable)
        rate = Decimal(item.tax_rate if taxable else 0)
        tax = (line_subtotal * rate / Decimal("100")) if taxable else Decimal("0")
        item.tax_amount = tax
        item.total_price = line_subtotal
        subtotal += line_subtotal
        tax_total += tax
    requisition.subtotal = subtotal
    requisition.tax_amount = tax_total
    requisition.total_amount = subtotal + tax_total
    db.commit()
    db.refresh(requisition)
    return requisition


@router.get("")
def list_requisitions(
    scope: str = Query(default="active", pattern="^(active|history|all)$"),
    status: str | None = Query(default=None, max_length=30),
    search: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    user=Depends(pr_view_user),
):
    scoped = apply_location_scope(
        _apply_scope(db.query(PurchaseRequisition), scope),
        PurchaseRequisition.location_id,
        user,
    )
    status_counts = dict(
        scoped.with_entities(PurchaseRequisition.status, func.count(PurchaseRequisition.id))
        .group_by(PurchaseRequisition.status)
        .all()
    )
    this_month_prefix = date.today().strftime("%Y-%m")
    this_month = scoped.filter(func.to_char(PurchaseRequisition.request_date, "YYYY-MM") == this_month_prefix).count()

    query = apply_location_scope(
        _apply_scope(db.query(PurchaseRequisition, User.full_name), scope),
        PurchaseRequisition.location_id,
        user,
    ).outerjoin(User, User.id == PurchaseRequisition.requested_by_id)
    if status and status.upper() != "ALL":
        query = query.filter(PurchaseRequisition.status == status.upper())
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(or_(PurchaseRequisition.pr_number.ilike(term), User.full_name.ilike(term)))

    total = query.count()
    rows = query.order_by(PurchaseRequisition.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    total_pages = ceil(total / page_size) if total else 0
    return {
        "items": [_list_row(db, requisition, requester_name) for requisition, requester_name in rows],
        "page": page,
        "page_size": page_size,
        "total_items": total,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_previous": page > 1,
        "summary": {
            "status_counts": status_counts,
            "this_month": this_month,
        },
    }


@router.get("/eligible-for-po")
def list_requisitions_eligible_for_po(db: Session = Depends(get_db), user=Depends(pr_convert_user)):
    requisitions = (
        apply_location_scope(
            db.query(PurchaseRequisition),
            PurchaseRequisition.location_id,
            user,
        )
        .filter(PurchaseRequisition.status.in_({"APPROVED", "PARTIALLY_CONVERTED"}))
        .order_by(PurchaseRequisition.id.desc())
        .all()
    )
    result = []
    for requisition in requisitions:
        payload = {
            "id": requisition.id,
            "pr_number": requisition.pr_number,
            "status": requisition.status,
            "request_date": requisition.request_date,
            "expiry_date": requisition.expiry_date,
            "notes": requisition.notes,
            "subtotal": requisition.subtotal,
            "tax_amount": requisition.tax_amount,
            "total_amount": requisition.total_amount,
            **_organization_context(db, requisition),
            "items": [],
        }
        for item in requisition.items:
            already_ordered = db.query(func.coalesce(func.sum(PurchaseOrderItem.quantity), 0)).join(PurchaseOrder).filter(PurchaseOrderItem.purchase_requisition_item_id == item.id, PurchaseOrder.status.notin_(["CANCELLED", "ARCHIVED", "REJECTED"])).scalar() or 0
            remaining = item.quantity - already_ordered
            if remaining <= 0:
                continue
            payload["items"].append({
                "id": item.id,
                "product_id": item.product_id,
                "product_code": item.product_code,
                "product_name": item.product_name,
                "description": item.product.description,
                "uom": item.product_uom,
                "quantity": item.quantity,
                "remaining_quantity": remaining,
                "estimated_price": item.estimated_price,
                "total_price": item.total_price,
                "is_taxable": item.is_taxable,
                "tax_rate": item.tax_rate,
                "tax_amount": item.tax_amount,
                "line_total": Decimal(item.total_price) + Decimal(item.tax_amount or 0),
            })
        # Corrupted legacy headers (non-zero totals but no surviving lines) must
        # never be offered for PO conversion. They require backup-based recovery.
        if payload["items"]:
            result.append(payload)
    return result


@router.get("/{requisition_id}")
def get_requisition(requisition_id: int, db: Session = Depends(get_db), user=Depends(pr_view_user)):
    requisition = db.get(PurchaseRequisition, requisition_id)
    if not requisition:
        raise HTTPException(status_code=404, detail="Purchase requisition not found")
    require_location_access(requisition.location_id, user)
    requester = db.get(User, requisition.requested_by_id) if requisition.requested_by_id else None
    result = {
        "id": requisition.id,
        "pr_number": requisition.pr_number,
        "status": requisition.status,
        "request_date": requisition.request_date,
        "requester_name": requester.full_name if requester else None,
        "source_type": requisition.source_type,
        "external_reference": requisition.external_reference,
        "expiry_date": requisition.expiry_date,
        "notes": requisition.notes,
        "subtotal": requisition.subtotal,
        "tax_amount": requisition.tax_amount,
        "total_amount": requisition.total_amount,
        **_organization_context(db, requisition),
        "created_at": requisition.created_at,
        "updated_at": requisition.updated_at,
        "items": [{
            "id": item.id,
            "product_id": item.product_id,
            "product_code": item.product_code,
            "product_name": item.product_name,
            "uom": item.product_uom,
            "quantity": item.quantity,
            "estimated_price": item.estimated_price,
            "total_price": item.total_price,
            "is_taxable": item.is_taxable,
            "tax_rate": item.tax_rate,
            "tax_amount": item.tax_amount,
            "line_total": Decimal(item.total_price) + Decimal(item.tax_amount or 0),
        } for item in requisition.items],
        "generated_purchase_orders": [{"id": order.id, "document_number": order.po_number, "status": order.status} for order in requisition.purchase_orders],
        "integrity_status": (
            "MISSING_ITEMS"
            if not requisition.items and Decimal(requisition.total_amount or 0) != 0
            else "OK"
        ),
    }
    result.update(document_context(db, "PURCHASE_REQUISITION", requisition.id, requisition.status, user))
    return result


@router.get("/{requisition_id}/print")
def print_requisition(requisition_id: int, db: Session = Depends(get_db), user=Depends(pr_view_user)):
    return {**get_requisition(requisition_id, db, user), "document_type": "Purchase Requisition", **print_metadata(user), **print_context(db,user,"PURCHASE_REQUISITION",requisition_id)}


def _apply_login_organization_context(db: Session, data: PurchaseRequisitionCreate, user) -> None:
    """Use the user's persisted organization identity for operational PR creation."""
    if is_superuser(user):
        data.location_id = resolve_location_id(user, data.location_id)
        return

    location_id = user.default_location_id or user.location_id
    department_id = user.default_department_id or user.department_id
    business_unit_id = user.default_business_unit_id

    location = db.get(Location, location_id) if location_id else None
    department = db.get(Department, department_id) if department_id else None

    if location:
        if not location.is_active:
            raise HTTPException(409, "Assigned work location is inactive")
        business_unit_id = business_unit_id or location.business_unit_id
        data.location_id = location.id
    else:
        data.location_id = resolve_location_id(user, data.location_id)

    if department:
        if not department.is_active:
            raise HTTPException(409, "Assigned department is inactive")
        if business_unit_id is None:
            business_unit_id = department.business_unit_id
        elif department.business_unit_id not in {None, business_unit_id}:
            raise HTTPException(409, "Assigned department does not belong to the user's Business Unit")
        if location:
            mapped = (
                db.query(LocationDepartment)
                .filter(
                    LocationDepartment.location_id == location.id,
                    LocationDepartment.department_id == department.id,
                )
                .first()
            )
            if not mapped:
                department = None
        if department:
            data.department_id = department.id

    if business_unit_id is not None:
        business_unit = db.get(BusinessUnit, business_unit_id)
        if not business_unit or not business_unit.is_active:
            raise HTTPException(409, "Assigned Business Unit is inactive or missing")
        if location and location.business_unit_id != business_unit_id:
            raise HTTPException(409, "Assigned location does not belong to the user's Business Unit")
        data.business_unit_id = business_unit_id


@router.post("", status_code=201)
def create_requisition(data: PurchaseRequisitionCreate, db: Session = Depends(get_db), user=Depends(pr_create_user)):
    _apply_login_organization_context(db, data, user)
    requisition = PurchaseRequisitionService.create(db=db, data=data, current_user=user)
    return _apply_tax(db, requisition, data)


@router.put("/{requisition_id}")
@router.patch("/{requisition_id}")
def update_requisition(requisition_id: int, data: PurchaseRequisitionCreate, db: Session = Depends(get_db), user=Depends(pr_edit_user)):
    existing = db.get(PurchaseRequisition, requisition_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Purchase requisition not found")
    require_location_access(existing.location_id, user)
    requisition = PurchaseRequisitionService.update(db=db, purchase_requisition_id=requisition_id, data=data, current_user=user)
    return _apply_tax(db, requisition, data)


@router.post("/{requisition_id}/reopen")
def reopen_requisition(requisition_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not is_superuser(user):
        raise HTTPException(status_code=403, detail="Only an administrator can reopen a purchase requisition")
    requisition = db.get(PurchaseRequisition, requisition_id)
    if not requisition:
        raise HTTPException(status_code=404, detail="Purchase requisition not found")
    if requisition.status == "DRAFT":
        raise HTTPException(status_code=409, detail="Purchase requisition is already draft")
    active_orders = [order for order in requisition.purchase_orders if order.status != "CANCELLED"]
    if active_orders:
        numbers = ", ".join(order.po_number for order in active_orders[:5])
        raise HTTPException(status_code=409, detail=f"Purchase requisition has active downstream purchase order(s): {numbers}. Cancel or correct those documents first.")
    previous_status = requisition.status
    reset_approval(db, "PURCHASE_REQUISITION", requisition.id)
    requisition.status = "DRAFT"
    AuditService.log(db=db, user=user, action="REOPEN", entity_type="PURCHASE_REQUISITION", entity_id=requisition.id, summary=f"Reopened {requisition.pr_number} for correction", document_type="PR", document_number=requisition.pr_number, document_status="DRAFT", details={"previous_status": previous_status, "admin_override": True})
    db.commit()
    db.refresh(requisition)
    return get_requisition(requisition.id, db, user)


@router.post("/{requisition_id}/submit")
def submit_requisition(requisition_id: int, db: Session = Depends(get_db), user=Depends(pr_submit_user)):
    requisition = db.get(PurchaseRequisition, requisition_id)
    if not requisition:
        raise HTTPException(status_code=404, detail="Purchase requisition not found")
    require_location_access(requisition.location_id, user)
    return PurchaseRequisitionService.submit(db=db, purchase_requisition_id=requisition_id, current_user=user)


@router.post("/{requisition_id}/approve")
def approve_requisition(requisition_id: int, data: ApprovalDecisionRequest | None = None, db: Session = Depends(get_db), user=Depends(pr_approve_user)):
    requisition = db.get(PurchaseRequisition, requisition_id)
    if not requisition:
        raise HTTPException(status_code=404, detail="Purchase requisition not found")
    require_location_access(requisition.location_id, user)
    return PurchaseRequisitionService.approve(db=db, purchase_requisition_id=requisition_id, data=data, current_user=user)


@router.post("/{requisition_id}/reject")
def reject_requisition(requisition_id: int, data: ApprovalDecisionRequest | None = None, db: Session = Depends(get_db), user=Depends(pr_approve_user)):
    requisition = db.get(PurchaseRequisition, requisition_id)
    if not requisition:
        raise HTTPException(status_code=404, detail="Purchase requisition not found")
    require_location_access(requisition.location_id, user)
    return PurchaseRequisitionService.reject(db=db, purchase_requisition_id=requisition_id, data=data, current_user=user)


@router.post("/{requisition_id}/convert-to-po")
def convert_requisition(requisition_id: int, data: PurchaseRequisitionConvertCreate, db: Session = Depends(get_db), user=Depends(pr_convert_user)):
    requisition = db.get(PurchaseRequisition, requisition_id)
    if not requisition:
        raise HTTPException(status_code=404, detail="Purchase requisition not found")
    require_location_access(requisition.location_id, user)
    return PurchaseRequisitionService.convert_to_purchase_order(db=db, purchase_requisition_id=requisition_id, data=data, current_user=user)
