from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.purchase_requisition import PurchaseRequisition
from app.schemas.approval import ApprovalDecisionRequest
from app.schemas.purchase_requisition import (
    PurchaseRequisitionConvertCreate,
    PurchaseRequisitionCreate,
)
from app.services.purchase_requisition_service import PurchaseRequisitionService


router = APIRouter(prefix="/purchase-requisitions", tags=["Purchase Requisitions"])


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
        .filter(PurchaseRequisition.status == "APPROVED")
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
        }
        for requisition in requisitions
    ]

@router.get("/{requisition_id}")
def get_requisition(
    requisition_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    requisition = db.get(PurchaseRequisition, requisition_id)
    if not requisition:
        raise HTTPException(status_code=404, detail="Purchase requisition not found")

    return {
        "id": requisition.id,
        "pr_number": requisition.pr_number,
        "status": requisition.status,
        "request_date": requisition.request_date,
        "source_type": requisition.source_type,
        "external_reference": requisition.external_reference,
        "expiry_date": requisition.expiry_date,
        "notes": requisition.notes,
        "total_amount": requisition.total_amount,
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
    }

@router.post("", status_code=201)
def create_requisition(
    data: PurchaseRequisitionCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return PurchaseRequisitionService.create(db=db, data=data, current_user=user)


@router.post("/{requisition_id}/submit")
def submit_requisition(
    requisition_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
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
    user=Depends(get_current_user),
):
    return PurchaseRequisitionService.convert_to_purchase_order(
        db=db,
        purchase_requisition_id=requisition_id,
        data=data,
        current_user=user,
    )
