from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import require_roles
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
    return [
        {
            "id": requisition.id,
            "pr_number": requisition.pr_number,
            "status": requisition.status,
            "request_date": requisition.request_date,
            "expiry_date": requisition.expiry_date,
            "notes": requisition.notes,
            "total_amount": requisition.total_amount,
            "business_unit_id": requisition.business_unit_id,
            "business_unit_name": requisition.business_unit.name if requisition.business_unit else None,
            "department_id": requisition.department_id,
            "department_name": requisition.department.name if requisition.department else None,
            "location_id": requisition.location_id,
            "location_name": requisition.location.name if requisition.location else None,
            "items": [
                {
                    "id": item.id,
                    "product_id": item.product_id,
                    "product_code": item.product_code,
                    "product_name": item.product_name,
                    "description": item.product.description,
                    "uom": item.product_uom,
                    "quantity": item.quantity,
                    "remaining_quantity": item.quantity - (db.query(func.coalesce(func.sum(PurchaseOrderItem.quantity), 0)).join(PurchaseOrder).filter(
                        PurchaseOrderItem.purchase_requisition_item_id == item.id,
                        PurchaseOrder.status != "CANCELLED",
                    ).scalar() or 0),
                    "estimated_price": item.estimated_price,
                    "total_price": item.total_price,
                }
                for item in requisition.items
                if item.quantity > (db.query(func.coalesce(func.sum(PurchaseOrderItem.quantity), 0)).join(PurchaseOrder).filter(
                    PurchaseOrderItem.purchase_requisition_item_id == item.id,
                    PurchaseOrder.status != "CANCELLED",
                ).scalar() or 0)
            ],
        }
        for requisition in requisitions
    ]


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
        "business_unit_id": requisition.business_unit_id,
        "business_unit_name": requisition.business_unit.name if requisition.business_unit else None,
        "department_id": requisition.department_id,
        "department_name": requisition.department.name if requisition.department else None,
        "location_id": requisition.location_id,
        "location_name": requisition.location.name if requisition.location else None,
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
def print_requisition(requisition_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
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
def update_requisition(requisition_id: int, data: PurchaseRequisitionCreate,
                       db: Session = Depends(get_db), user=Depends(requester_user)):
    return PurchaseRequisitionService.update(db=db, purchase_requisition_id=requisition_id,
        data=data, current_user=user)


@router.post("/{requisition_id}/submit")
def submit_requisition(
    requisition_id: int,
    db: Session = Depends(get_db),
    user=Depends(requester_user),
):
    return PurchaseRequisitionService.submit(
        db=db, purchase_requisition_id=requisition_id, current_user=user
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
