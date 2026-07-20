from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.purchase_requisition import PurchaseRequisition
from app.models.purchase_requisition_item import PurchaseRequisitionItem
from app.models.supplier import Supplier
from app.services.audit import record_audit
from app.services.approval import (
    approve_current_step,
    get_request,
    reject_current_step,
    start_approval,
)
from app.schemas.purchase_order import PurchaseOrderCreate, PurchaseOrderResponse
from app.schemas.approval import ApprovalDecisionRequest

router = APIRouter(prefix="/purchase-orders", tags=["Purchase Orders"])


def generate_po_number(db: Session) -> str:
    count = db.query(PurchaseOrder).count() + 1
    return f"PO-{count:06d}"


def get_po_query(db: Session):
    return (
        db.query(PurchaseOrder)
        .options(
            joinedload(PurchaseOrder.items),
            joinedload(PurchaseOrder.purchase_requisitions),
        )
    )


@router.get("", response_model=list[PurchaseOrderResponse])
def get_purchase_orders(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return get_po_query(db).order_by(PurchaseOrder.id.desc()).all()


@router.post("", response_model=PurchaseOrderResponse, status_code=201)
def create_purchase_order(
    data: PurchaseOrderCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    supplier = db.query(Supplier).filter(Supplier.id == data.supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    if not data.items:
        raise HTTPException(status_code=400, detail="Purchase order must have items")

    if data.expiry_date and data.expiry_date < date.today():
        raise HTTPException(status_code=400, detail="PO expiry date cannot be in the past")

    requisitions = []
    if data.purchase_requisition_ids:
        requisitions = (
            db.query(PurchaseRequisition)
            .filter(PurchaseRequisition.id.in_(data.purchase_requisition_ids))
            .all()
        )
        if len(requisitions) != len(set(data.purchase_requisition_ids)):
            raise HTTPException(status_code=404, detail="One or more purchase requisitions not found")

        invalid = [pr for pr in requisitions if pr.status not in {"APPROVED", "CONVERTED"}]
        if invalid:
            raise HTTPException(status_code=400, detail="Only approved purchase requisitions can be used for a PO")

    purchase_order = PurchaseOrder(
        po_number=generate_po_number(db),
        supplier_id=data.supplier_id,
        expected_date=data.expected_date,
        expiry_date=data.expiry_date,
        receipt_tolerance_percent=data.receipt_tolerance_percent,
        notes=data.notes,
        status="DRAFT",
        total_amount=Decimal("0"),
        purchase_requisitions=requisitions,
    )

    total_amount = Decimal("0")
    source_pr_ids = set(data.purchase_requisition_ids)

    for item_data in data.items:
        product = db.query(Product).filter(Product.id == item_data.product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product {item_data.product_id} not found")

        if item_data.quantity <= 0:
            raise HTTPException(status_code=400, detail="Quantity must be greater than zero")

        if item_data.unit_price < 0:
            raise HTTPException(status_code=400, detail="Unit price cannot be negative")

        requisition_item = None
        if item_data.purchase_requisition_item_id is not None:
            requisition_item = (
                db.query(PurchaseRequisitionItem)
                .filter(PurchaseRequisitionItem.id == item_data.purchase_requisition_item_id)
                .first()
            )
            if not requisition_item:
                raise HTTPException(status_code=404, detail="Purchase requisition item not found")
            if requisition_item.product_id != item_data.product_id:
                raise HTTPException(status_code=400, detail="PO product does not match PR item")
            if requisition_item.purchase_requisition_id not in source_pr_ids:
                raise HTTPException(status_code=400, detail="PR item must belong to a selected PR")

        total_price = item_data.quantity * item_data.unit_price
        purchase_order.items.append(
            PurchaseOrderItem(
                purchase_requisition_item_id=(
                    requisition_item.id if requisition_item else None
                ),
                product_id=item_data.product_id,
                quantity=item_data.quantity,
                received_quantity=Decimal("0"),
                unit_price=item_data.unit_price,
                total_price=total_price,
            )
        )
        total_amount += total_price

    purchase_order.total_amount = total_amount
    db.add(purchase_order)
    db.flush()

    for requisition in requisitions:
        if requisition.status == "APPROVED":
            requisition.status = "CONVERTED"

    record_audit(
        db=db,
        user=current_user,
        action="CREATE",
        entity_type="PURCHASE_ORDER",
        entity_id=purchase_order.id,
        summary=f"Created purchase order {purchase_order.po_number}",
        details={
            "po_number": purchase_order.po_number,
            "purchase_requisition_ids": data.purchase_requisition_ids,
            "supplier_id": purchase_order.supplier_id,
            "total_amount": str(purchase_order.total_amount),
            "expiry_date": str(purchase_order.expiry_date) if purchase_order.expiry_date else None,
            "receipt_tolerance_percent": str(purchase_order.receipt_tolerance_percent),
        },
    )

    db.commit()
    return get_po_query(db).filter(PurchaseOrder.id == purchase_order.id).first()


@router.patch("/{purchase_order_id}/submit", response_model=PurchaseOrderResponse)
def submit_purchase_order(
    purchase_order_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    purchase_order = db.query(PurchaseOrder).filter(PurchaseOrder.id == purchase_order_id).first()
    if not purchase_order:
        raise HTTPException(status_code=404, detail="Purchase order not found")

    if purchase_order.status != "DRAFT":
        raise HTTPException(status_code=400, detail="Only draft purchase orders can be submitted")

    start_approval(
        db,
        entity_type="PURCHASE_ORDER",
        entity_id=purchase_order.id,
        workflow_code="PO_APPROVAL",
        user=current_user,
    )
    purchase_order.status = "PENDING_APPROVAL"

    record_audit(
        db=db,
        user=current_user,
        action="SUBMIT",
        entity_type="PURCHASE_ORDER",
        entity_id=purchase_order.id,
        summary=f"Submitted purchase order {purchase_order.po_number} for approval",
        details={"status": purchase_order.status, "workflow": "PO_APPROVAL"},
    )

    db.commit()
    return get_po_query(db).filter(PurchaseOrder.id == purchase_order.id).first()


@router.patch("/{purchase_order_id}/approve", response_model=PurchaseOrderResponse)
def approve_purchase_order(
    purchase_order_id: int,
    data: ApprovalDecisionRequest | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    purchase_order = db.query(PurchaseOrder).filter(PurchaseOrder.id == purchase_order_id).first()
    if not purchase_order:
        raise HTTPException(status_code=404, detail="Purchase order not found")

    if purchase_order.status != "PENDING_APPROVAL":
        raise HTTPException(status_code=400, detail="Purchase order does not have a pending approval")

    request = get_request(db, "PURCHASE_ORDER", purchase_order.id)
    if not request:
        raise HTTPException(status_code=500, detail="Approval workflow not found")

    approve_current_step(
        db,
        request=request,
        user=current_user,
        comment=data.comment if data else None,
    )

    if request.status == "APPROVED":
        purchase_order.status = "APPROVED"

    record_audit(
        db=db,
        user=current_user,
        action="APPROVE",
        entity_type="PURCHASE_ORDER",
        entity_id=purchase_order.id,
        summary=f"Approved PO approval step for {purchase_order.po_number}",
        details={
            "approval_status": request.status,
            "current_step_order": request.current_step_order,
            "comment": data.comment if data else None,
        },
    )

    db.commit()
    return get_po_query(db).filter(PurchaseOrder.id == purchase_order.id).first()


@router.patch("/{purchase_order_id}/reject", response_model=PurchaseOrderResponse)
def reject_purchase_order(
    purchase_order_id: int,
    data: ApprovalDecisionRequest | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    purchase_order = db.query(PurchaseOrder).filter(PurchaseOrder.id == purchase_order_id).first()
    if not purchase_order:
        raise HTTPException(status_code=404, detail="Purchase order not found")

    if purchase_order.status != "PENDING_APPROVAL":
        raise HTTPException(status_code=400, detail="Purchase order does not have a pending approval")

    request = get_request(db, "PURCHASE_ORDER", purchase_order.id)
    if not request:
        raise HTTPException(status_code=500, detail="Approval workflow not found")

    reject_current_step(
        db,
        request=request,
        user=current_user,
        comment=data.comment if data else None,
    )
    purchase_order.status = "REJECTED"

    record_audit(
        db=db,
        user=current_user,
        action="REJECT",
        entity_type="PURCHASE_ORDER",
        entity_id=purchase_order.id,
        summary=f"Rejected {purchase_order.po_number}",
        details={"comment": data.comment if data else None},
    )

    db.commit()
    return get_po_query(db).filter(PurchaseOrder.id == purchase_order.id).first()
