from decimal import Decimal

import sqlalchemy as sa

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.dependencies.auth import get_current_user

from app.models.audit_log import AuditLog
from app.models.goods_receipt import GoodsReceipt
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import (
    PurchaseOrderItem,
)
from app.models.purchase_requisition import (
    PurchaseRequisition,
)
from app.models.purchase_requisition_item import (
    PurchaseRequisitionItem,
)
from app.models.supplier import Supplier
from app.models.stock_movement import StockMovement
from app.services.audit import record_audit
from app.services.approval import (
    approve_current_step,
    get_request,
    reject_current_step,
    start_approval,
)

from app.schemas.purchase_requisition import (
    PurchaseRequisitionConvertCreate,
    PurchaseRequisitionCreate,
    PurchaseRequisitionResponse,
    PurchaseRequisitionTraceabilityResponse,
    TraceabilityEventResponse,
    TraceabilityGoodsReceiptResponse,
    TraceabilityPurchaseOrderResponse,
    TraceabilityStockMovementResponse,
)
from app.schemas.approval import ApprovalDecisionRequest


router = APIRouter(
    prefix="/purchase-requisitions",
    tags=["Purchase Requisitions"],
)


def generate_pr_number(db: Session) -> str:
    count = (
        db.query(PurchaseRequisition)
        .count()
        + 1
    )

    return f"PR-{count:06d}"


def generate_po_number(db: Session) -> str:
    count = (
        db.query(PurchaseOrder)
        .count()
        + 1
    )

    return f"PO-{count:06d}"


@router.get(
    "",
    response_model=list[
        PurchaseRequisitionResponse
    ],
)
def get_purchase_requisitions(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return (
        db.query(PurchaseRequisition)
        .options(
            joinedload(PurchaseRequisition.items).joinedload(
                PurchaseRequisitionItem.product
            )
        )
        .order_by(
            PurchaseRequisition.id.desc()
        )
        .all()
    )


@router.get(
    "/{purchase_requisition_id}",
    response_model=PurchaseRequisitionResponse,
)
def get_purchase_requisition(
    purchase_requisition_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    purchase_requisition = (
        db.query(PurchaseRequisition)
        .options(
            joinedload(PurchaseRequisition.items).joinedload(
                PurchaseRequisitionItem.product
            )
        )
        .filter(
            PurchaseRequisition.id
            == purchase_requisition_id
        )
        .first()
    )

    if not purchase_requisition:
        raise HTTPException(
            status_code=404,
            detail="Purchase requisition not found",
        )

    return purchase_requisition




@router.get(
    "/{purchase_requisition_id}/traceability",
    response_model=PurchaseRequisitionTraceabilityResponse,
)
def get_purchase_requisition_traceability(
    purchase_requisition_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    purchase_requisition = (
        db.query(PurchaseRequisition)
        .filter(
            PurchaseRequisition.id
            == purchase_requisition_id
        )
        .first()
    )

    if not purchase_requisition:
        raise HTTPException(
            status_code=404,
            detail="Purchase requisition not found",
        )

    purchase_orders = (
        db.query(PurchaseOrder)
        .join(PurchaseOrder.purchase_requisitions)
        .filter(
            PurchaseRequisition.id == purchase_requisition.id,
        )
        .order_by(PurchaseOrder.id)
        .all()
    )

    purchase_order_ids = [
        purchase_order.id
        for purchase_order in purchase_orders
    ]

    goods_receipts = (
        db.query(GoodsReceipt)
        .filter(
            GoodsReceipt.purchase_order_id.in_(
                purchase_order_ids
            )
        )
        .order_by(GoodsReceipt.id)
        .all()
        if purchase_order_ids
        else []
    )

    goods_receipt_ids = [
        receipt.id
        for receipt in goods_receipts
    ]

    movement_filters = []

    if goods_receipt_ids:
        movement_filters.append(
            StockMovement.goods_receipt_id.in_(
                goods_receipt_ids
            )
        )

    if purchase_order_ids:
        movement_filters.append(
            sa.and_(
                StockMovement.reference_type
                == "PURCHASE_ORDER",
                StockMovement.reference_id.in_(
                    purchase_order_ids
                ),
            )
        )

    stock_movements = (
        db.query(StockMovement)
        .filter(sa.or_(*movement_filters))
        .order_by(StockMovement.id)
        .all()
        if movement_filters
        else []
    )

    audit_filters = [
        (
            AuditLog.entity_type
            == "PURCHASE_REQUISITION"
        )
        & (
            AuditLog.entity_id
            == purchase_requisition.id
        )
    ]

    if purchase_order_ids:
        audit_filters.append(
            (
                AuditLog.entity_type
                == "PURCHASE_ORDER"
            )
            & AuditLog.entity_id.in_(
                purchase_order_ids
            )
        )

    if goods_receipt_ids:
        audit_filters.append(
            (
                AuditLog.entity_type
                == "GOODS_RECEIPT"
            )
            & AuditLog.entity_id.in_(
                goods_receipt_ids
            )
        )

    movement_ids = [
        movement.id
        for movement in stock_movements
    ]

    if movement_ids:
        audit_filters.append(
            (
                AuditLog.entity_type
                == "STOCK_MOVEMENT"
            )
            & AuditLog.entity_id.in_(movement_ids)
        )

    logs = (
        db.query(AuditLog)
        .options(joinedload(AuditLog.user))
        .filter(
            sa.or_(*audit_filters)
        )
        .order_by(AuditLog.created_at)
        .all()
    )

    return PurchaseRequisitionTraceabilityResponse(
        purchase_requisition_id=purchase_requisition.id,
        pr_number=purchase_requisition.pr_number,
        purchase_orders=[
            TraceabilityPurchaseOrderResponse(
                id=order.id,
                po_number=order.po_number,
                status=order.status,
            )
            for order in purchase_orders
        ],
        goods_receipts=[
            TraceabilityGoodsReceiptResponse(
                id=receipt.id,
                receipt_number=receipt.receipt_number,
                purchase_order_id=receipt.purchase_order_id,
            )
            for receipt in goods_receipts
        ],
        stock_movements=[
            TraceabilityStockMovementResponse(
                id=movement.id,
                product_id=movement.product_id,
                quantity=movement.quantity,
                goods_receipt_id=movement.goods_receipt_id,
            )
            for movement in stock_movements
        ],
        events=[
            TraceabilityEventResponse(
                id=log.id,
                action=log.action,
                entity_type=log.entity_type,
                entity_id=log.entity_id,
                summary=log.summary,
                user_name=(
                    log.user.full_name
                    if log.user
                    else None
                ),
                created_at=log.created_at.isoformat(),
            )
            for log in logs
        ],
    )


@router.post(
    "",
    response_model=PurchaseRequisitionResponse,
    status_code=201,
)
def create_purchase_requisition(
    data: PurchaseRequisitionCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not data.items:
        raise HTTPException(
            status_code=400,
            detail=(
                "Purchase requisition must have items"
            ),
        )

    purchase_requisition = PurchaseRequisition(
        pr_number=generate_pr_number(db),
        status="DRAFT",
        notes=data.notes,
        total_amount=Decimal("0"),
    )

    total_amount = Decimal("0")

    for item_data in data.items:
        product = (
            db.query(Product)
            .filter(
                Product.id
                == item_data.product_id
            )
            .first()
        )

        if not product:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Product "
                    f"{item_data.product_id} "
                    f"not found"
                ),
            )

        if item_data.quantity <= 0:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Quantity must be greater "
                    "than zero"
                ),
            )

        if item_data.estimated_price < 0:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Estimated price cannot "
                    "be negative"
                ),
            )

        total_price = (
            item_data.quantity
            * item_data.estimated_price
        )

        purchase_requisition.items.append(
            PurchaseRequisitionItem(
                product_id=item_data.product_id,
                quantity=item_data.quantity,
                estimated_price=(
                    item_data.estimated_price
                ),
                total_price=total_price,
            )
        )

        total_amount += total_price

    purchase_requisition.total_amount = (
        total_amount
    )

    db.add(purchase_requisition)
    db.flush()

    record_audit(
        db=db,
        user=current_user,
        action="CREATE",
        entity_type="PURCHASE_REQUISITION",
        entity_id=purchase_requisition.id,
        summary=f"Created purchase requisition {purchase_requisition.pr_number}",
        details={
            "pr_number": purchase_requisition.pr_number,
            "total_amount": str(purchase_requisition.total_amount),
        },
    )

    db.commit()
    db.refresh(purchase_requisition)

    return purchase_requisition


@router.patch(
    "/{purchase_requisition_id}/submit",
    response_model=PurchaseRequisitionResponse,
)
def submit_purchase_requisition(
    purchase_requisition_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    purchase_requisition = (
        db.query(PurchaseRequisition)
        .filter(PurchaseRequisition.id == purchase_requisition_id)
        .first()
    )

    if not purchase_requisition:
        raise HTTPException(status_code=404, detail="Purchase requisition not found")

    if purchase_requisition.status != "DRAFT":
        raise HTTPException(
            status_code=400,
            detail="Only draft purchase requisitions can be submitted",
        )

    if not purchase_requisition.items:
        raise HTTPException(
            status_code=400,
            detail="Purchase requisition must have at least one item",
        )

    start_approval(
        db,
        entity_type="PURCHASE_REQUISITION",
        entity_id=purchase_requisition.id,
        workflow_code="PR_APPROVAL",
        user=current_user,
    )
    purchase_requisition.status = "PENDING_APPROVAL"

    record_audit(
        db=db,
        user=current_user,
        action="SUBMIT",
        entity_type="PURCHASE_REQUISITION",
        entity_id=purchase_requisition.id,
        summary=f"Submitted purchase requisition {purchase_requisition.pr_number} for approval",
        details={"status": purchase_requisition.status, "workflow": "PR_APPROVAL"},
    )

    db.commit()
    db.refresh(purchase_requisition)
    return purchase_requisition


@router.patch(
    "/{purchase_requisition_id}/approve",
    response_model=PurchaseRequisitionResponse,
)
def approve_purchase_requisition(
    purchase_requisition_id: int,
    data: ApprovalDecisionRequest | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    purchase_requisition = (
        db.query(PurchaseRequisition)
        .filter(PurchaseRequisition.id == purchase_requisition_id)
        .first()
    )

    if not purchase_requisition:
        raise HTTPException(status_code=404, detail="Purchase requisition not found")

    if purchase_requisition.status != "PENDING_APPROVAL":
        raise HTTPException(
            status_code=400,
            detail="Purchase requisition does not have a pending approval",
        )

    request = get_request(db, "PURCHASE_REQUISITION", purchase_requisition.id)
    if not request:
        raise HTTPException(status_code=500, detail="Approval workflow not found")

    approve_current_step(
        db,
        request=request,
        user=current_user,
        comment=data.comment if data else None,
    )

    if request.status == "APPROVED":
        purchase_requisition.status = "APPROVED"

    record_audit(
        db=db,
        user=current_user,
        action="APPROVE",
        entity_type="PURCHASE_REQUISITION",
        entity_id=purchase_requisition.id,
        summary=f"Approved PR approval step for {purchase_requisition.pr_number}",
        details={
            "approval_status": request.status,
            "current_step_order": request.current_step_order,
            "comment": data.comment if data else None,
        },
    )

    db.commit()
    db.refresh(purchase_requisition)
    return purchase_requisition


@router.patch(
    "/{purchase_requisition_id}/reject",
    response_model=PurchaseRequisitionResponse,
)
def reject_purchase_requisition(
    purchase_requisition_id: int,
    data: ApprovalDecisionRequest | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    purchase_requisition = (
        db.query(PurchaseRequisition)
        .filter(PurchaseRequisition.id == purchase_requisition_id)
        .first()
    )

    if not purchase_requisition:
        raise HTTPException(status_code=404, detail="Purchase requisition not found")

    if purchase_requisition.status != "PENDING_APPROVAL":
        raise HTTPException(
            status_code=400,
            detail="Purchase requisition does not have a pending approval",
        )

    request = get_request(db, "PURCHASE_REQUISITION", purchase_requisition.id)
    if not request:
        raise HTTPException(status_code=500, detail="Approval workflow not found")

    reject_current_step(
        db,
        request=request,
        user=current_user,
        comment=data.comment if data else None,
    )
    purchase_requisition.status = "REJECTED"

    record_audit(
        db=db,
        user=current_user,
        action="REJECT",
        entity_type="PURCHASE_REQUISITION",
        entity_id=purchase_requisition.id,
        summary=f"Rejected {purchase_requisition.pr_number}",
        details={"comment": data.comment if data else None},
    )

    db.commit()
    db.refresh(purchase_requisition)
    return purchase_requisition


@router.post(
    "/{purchase_requisition_id}/convert-to-po",
)
def convert_purchase_requisition_to_purchase_order(
    purchase_requisition_id: int,
    data: PurchaseRequisitionConvertCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    purchase_requisition = (
        db.query(PurchaseRequisition)
        .filter(
            PurchaseRequisition.id
            == purchase_requisition_id
        )
        .first()
    )

    if not purchase_requisition:
        raise HTTPException(
            status_code=404,
            detail="Purchase requisition not found",
        )

    if purchase_requisition.status != "APPROVED":
        raise HTTPException(
            status_code=400,
            detail=(
                "Only approved purchase "
                "requisitions can be converted "
                "to purchase orders"
            ),
        )

    supplier = (
        db.query(Supplier)
        .filter(
            Supplier.id == data.supplier_id
        )
        .first()
    )

    if not supplier:
        raise HTTPException(
            status_code=404,
            detail="Supplier not found",
        )

    if not purchase_requisition.items:
        raise HTTPException(
            status_code=400,
            detail=(
                "Purchase requisition must have "
                "at least one item"
            ),
        )

    purchase_order = PurchaseOrder(
        po_number=generate_po_number(db),
        supplier_id=data.supplier_id,
        status="DRAFT",
        total_amount=Decimal("0"),
        notes=(
            f"Created from "
            f"{purchase_requisition.pr_number}"
        ),
        purchase_requisitions=[purchase_requisition],
    )

    total_amount = Decimal("0")

    for item in purchase_requisition.items:
        total_price = (
            item.quantity
            * item.estimated_price
        )

        purchase_order.items.append(
            PurchaseOrderItem(
                purchase_requisition_item_id=item.id,
                product_id=item.product_id,
                quantity=item.quantity,
                received_quantity=Decimal("0"),
                unit_price=item.estimated_price,
                total_price=total_price,
            )
        )

        total_amount += total_price

    purchase_order.total_amount = total_amount

    purchase_requisition.status = "CONVERTED"

    db.add(purchase_order)
    db.flush()

    record_audit(
        db=db,
        user=current_user,
        action="CONVERT",
        entity_type="PURCHASE_REQUISITION",
        entity_id=purchase_requisition.id,
        summary=f"Converted {purchase_requisition.pr_number} to {purchase_order.po_number}",
        details={
            "pr_number": purchase_requisition.pr_number,
            "po_number": purchase_order.po_number,
            "purchase_order_id": purchase_order.id,
        },
    )

    record_audit(
        db=db,
        user=current_user,
        action="CREATE",
        entity_type="PURCHASE_ORDER",
        entity_id=purchase_order.id,
        summary=f"Created purchase order {purchase_order.po_number} from {purchase_requisition.pr_number}",
        details={
            "po_number": purchase_order.po_number,
            "purchase_requisition_id": purchase_requisition.id,
            "pr_number": purchase_requisition.pr_number,
            "supplier_id": purchase_order.supplier_id,
            "total_amount": str(purchase_order.total_amount),
        },
    )

    db.commit()
    db.refresh(purchase_order)

    return {
        "message": (
            "Purchase requisition converted "
            "to purchase order"
        ),
        "purchase_requisition_id": (
            purchase_requisition.id
        ),
        "purchase_order_id": purchase_order.id,
        "po_number": purchase_order.po_number,
        "status": purchase_order.status,
    }