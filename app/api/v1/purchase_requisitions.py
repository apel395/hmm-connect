from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import require_roles
from app.models.business_unit import BusinessUnit
from app.models.department import Department
from app.models.location import Location
from app.models.purchase_requisition import PurchaseRequisition
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.schemas.approval import ApprovalDecisionRequest
from app.schemas.purchase_requisition import (
    PurchaseRequisitionConvertCreate,
    PurchaseRequisitionCreate,
)
from app.services.purchase_requisition_service import PurchaseRequisitionService
from app.services.document_context import document_context, print_metadata


router = APIRouter(prefix="/purchase-requisitions", tags=["Purchase Requisitions"])
requester_user = require_roles("REQUESTER")
purchasing_user = require_roles("PURCHASING")


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


@router.get("")
def list_requisitions(
    scope: str = Query(default="active", pattern="^(active|history|all)$"),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    query = db.query(PurchaseRequisition)
    if scope == "active":
        query = query.filter(
            PurchaseRequisition.status.in_(
                {"DRAFT", "PENDING_APPROVAL", "APPROVED", "PARTIALLY_CONVERTED"}
            )
        )
    elif scope == "history":
        query = query.filter(
            PurchaseRequisition.status.in_(
                {"CONVERTED", "REJECTED", "CANCELLED", "EXPIRED"}
            )
        )
    return query.order_by(PurchaseRequisition.id.desc()).all()


@router.get("/eligible-for-po")
def list_requisitions_eligible_for_po(
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    requisitions = (
        db.query(PurchaseRequisition)
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
            "total_amount": requisition.total_amount,
            **_organization_context(db, requisition),
            "items": [],
        }
        for item in requisition.items:
            already_ordered = (
                db.query(func.coalesce(func.sum(PurchaseOrderItem.quantity), 0))
                .join(PurchaseOrder)
                .filter(
                    PurchaseOrderItem.purchase_requisition_item_id == item.id,
                    PurchaseOrder.status != "CANCELLED",
                )
                .scalar()
                or 0
            )
            remaining = item.quantity - already_ordered
            if remaining <= 0:
                continue
            payload["items"].append(
                {
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
                }
            )
        result.append(payload)
    return result


@router.get("/{requisition_id}")
def get_requisition(
    requisition_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    requisition = db.get(PurchaseRequisition, requisition_id)
    if not requisition:
        raise HTTPException(status_code=404, detail="Purchase requisition not found")

    result = {
        "id": requisition.id,
        "pr_number": requisition.pr_number,
        "status": requisition.status,
        "request_date": requisition.request_date,
        "source_type": requisition.source_type,
        "external_reference": requisition.external_reference,
        "expiry_date": requisition.expiry_date,
        "notes": requisition.notes,
        "total_amount": requisition.total_amount,
        **_organization_context(db, requisition),
        "created_at": requisition.created_at,
        "updated_at": requisition.updated_at,
        "items": [
            {
                "id": item.id,
                "product_id": item.product_id,
                "product_code": item.product_code,
                "product_name": item.product_name,
                "uom": item.product_uom,
                "quantity": item.quantity,
                "estimated_price": item.estimated_price,
                "total_price": item.total_price,
            }
            for item in requisition.items
        ],
        "generated_purchase_orders": [
            {"id": order.id, "document_number": order.po_number, "status": order.status}
            for order in requisition.purchase_orders
        ],
    }
    result.update(document_context(db, "PURCHASE_REQUISITION", requisition.id, requisition.status, user))
    return result


@router.get("/{requisition_id}/print")
def print_requisition(
    requisition_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    result = get_requisition(requisition_id, db, user)
    return {**result, "document_type": "Purchase Requisition", **print_metadata(user)}


@router.post("", status_code=201)
def create_requisition(
    data: PurchaseRequisitionCreate,
    db: Session = Depends(get_db),
    user=Depends(requester_user),
):
    return PurchaseRequisitionService.create(db=db, data=data, current_user=user)


@router.put("/{requisition_id}")
@router.patch("/{requisition_id}")
def update_requisition(
    requisition_id: int,
    data: PurchaseRequisitionCreate,
    db: Session = Depends(get_db),
    user=Depends(requester_user),
):
    return PurchaseRequisitionService.update(
        db=db,
        purchase_requisition_id=requisition_id,
        data=data,
        current_user=user,
    )


@router.post("/{requisition_id}/submit")
def submit_requisition(
    requisition_id: int,
    db: Session = Depends(get_db),
    user=Depends(requester_user),
):
    return PurchaseRequisitionService.submit(
        db=db,
        purchase_requisition_id=requisition_id,
        current_user=user,
    )


@router.post("/{requisition_id}/approve")
def approve_requisition(
    requisition_id: int,
    data: ApprovalDecisionRequest | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return PurchaseRequisitionService.approve(
        db=db,
        purchase_requisition_id=requisition_id,
        data=data,
        current_user=user,
    )


@router.post("/{requisition_id}/reject")
def reject_requisition(
    requisition_id: int,
    data: ApprovalDecisionRequest | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return PurchaseRequisitionService.reject(
        db=db,
        purchase_requisition_id=requisition_id,
        data=data,
        current_user=user,
    )


@router.post("/{requisition_id}/convert-to-po")
def convert_requisition(
    requisition_id: int,
    data: PurchaseRequisitionConvertCreate,
    db: Session = Depends(get_db),
    user=Depends(purchasing_user),
):
    return PurchaseRequisitionService.convert_to_purchase_order(
        db=db,
        purchase_requisition_id=requisition_id,
        data=data,
        current_user=user,
    )
