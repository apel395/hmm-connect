from fastapi import APIRouter, Depends
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
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    return db.query(PurchaseRequisition).order_by(PurchaseRequisition.id.desc()).all()


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
