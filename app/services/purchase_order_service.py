from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.purchase_requisition import PurchaseRequisition
from app.models.supplier import Supplier
from app.schemas.approval import ApprovalDecisionRequest
from app.schemas.purchase_order import PurchaseOrderCreate
from app.services.activity_service import AuditService
from app.services.approval import (
    approve_current_step,
    get_request,
    reject_current_step,
    start_approval,
)


class PurchaseOrderService:
    @staticmethod
    def _number(db: Session) -> str:
        return f"PO-{db.query(PurchaseOrder).count() + 1:06d}"

    @staticmethod
    def _audit(db, user, purchase_order, action, previous_status=None, **details):
        AuditService.log(
            db=db,
            user=user,
            action=action,
            entity_type="PURCHASE_ORDER",
            entity_id=purchase_order.id,
            summary=f"{action.title()} {purchase_order.po_number}",
            document_type="PO",
            document_number=purchase_order.po_number,
            document_status=purchase_order.status,
            details={"previous_status": previous_status, **details},
        )

    @staticmethod
    def create(db: Session, *, data: PurchaseOrderCreate, user):
        supplier = db.get(Supplier, data.supplier_id)
        if not supplier or not supplier.is_active:
            raise HTTPException(status_code=404, detail="Active supplier not found")

        requisitions = (
            db.query(PurchaseRequisition)
            .filter(PurchaseRequisition.id.in_(data.purchase_requisition_ids))
            .all()
        )
        if len(requisitions) != len(set(data.purchase_requisition_ids)):
            raise HTTPException(status_code=404, detail="Purchase requisition not found")
        if any(item.status != "APPROVED" for item in requisitions):
            raise HTTPException(
                status_code=409,
                detail="Only approved, unused purchase requisitions can be selected",
            )

        requisition_item_ids = {
            item.id for requisition in requisitions for item in requisition.items
        }
        if any(
            item.purchase_requisition_item_id not in requisition_item_ids
            for item in data.items
        ):
            raise HTTPException(
                status_code=400,
                detail="PO items must belong to the selected purchase requisitions",
            )

        purchase_order = PurchaseOrder(
            po_number=PurchaseOrderService._number(db),
            supplier_id=data.supplier_id,
            status="DRAFT",
            expected_date=data.expected_date,
            expiry_date=data.expiry_date,
            receipt_tolerance_percent=data.receipt_tolerance_percent,
            notes=data.notes,
            purchase_requisitions=requisitions,
        )
        total = Decimal("0")
        for item in data.items:
            line_total = item.quantity * item.unit_price
            purchase_order.items.append(
                PurchaseOrderItem(
                    purchase_requisition_item_id=item.purchase_requisition_item_id,
                    product_id=item.product_id,
                    quantity=item.quantity,
                    received_quantity=Decimal("0"),
                    unit_price=item.unit_price,
                    total_price=line_total,
                )
            )
            total += line_total
        purchase_order.total_amount = total
        for requisition in requisitions:
            requisition.status = "CONVERTED"

        db.add(purchase_order)
        db.flush()
        PurchaseOrderService._audit(
            db, user, purchase_order, "CREATE", purchase_requisition_ids=data.purchase_requisition_ids
        )
        db.commit()
        db.refresh(purchase_order)
        return purchase_order

    @staticmethod
    def submit(db: Session, *, purchase_order_id: int, user):
        purchase_order = db.get(PurchaseOrder, purchase_order_id)
        if not purchase_order:
            raise HTTPException(status_code=404, detail="Purchase order not found")
        if purchase_order.status != "DRAFT":
            raise HTTPException(status_code=409, detail="Only draft purchase orders can be submitted")
        if purchase_order.expiry_date and purchase_order.expiry_date < date.today():
            purchase_order.status = "EXPIRED"
            PurchaseOrderService._audit(db, user, purchase_order, "EXPIRE", "DRAFT")
            db.commit()
            raise HTTPException(status_code=409, detail="Purchase order has expired")
        start_approval(
            db,
            entity_type="PURCHASE_ORDER",
            entity_id=purchase_order.id,
            workflow_code="PO_APPROVAL",
            user=user,
        )
        purchase_order.status = "PENDING_APPROVAL"
        PurchaseOrderService._audit(db, user, purchase_order, "SUBMIT", "DRAFT")
        db.commit()
        db.refresh(purchase_order)
        return purchase_order

    @staticmethod
    def approve(db: Session, *, purchase_order_id: int, data: ApprovalDecisionRequest | None, user):
        purchase_order = db.get(PurchaseOrder, purchase_order_id)
        if not purchase_order:
            raise HTTPException(status_code=404, detail="Purchase order not found")
        if purchase_order.status != "PENDING_APPROVAL":
            raise HTTPException(status_code=409, detail="Purchase order does not have pending approval")
        request = get_request(db, "PURCHASE_ORDER", purchase_order.id)
        if not request:
            raise HTTPException(status_code=500, detail="Approval workflow not found")
        previous_status = purchase_order.status
        approve_current_step(
            db,
            request=request,
            user=user,
            comment=data.comment if data else None,
        )
        if request.status == "APPROVED":
            purchase_order.status = "APPROVED"
        PurchaseOrderService._audit(
            db,
            user,
            purchase_order,
            "APPROVE",
            previous_status,
            approval_status=request.status,
            comment=data.comment if data else None,
        )
        db.commit()
        db.refresh(purchase_order)
        return purchase_order

    @staticmethod
    def reject(db: Session, *, purchase_order_id: int, data: ApprovalDecisionRequest | None, user):
        purchase_order = db.get(PurchaseOrder, purchase_order_id)
        if not purchase_order:
            raise HTTPException(status_code=404, detail="Purchase order not found")
        if purchase_order.status != "PENDING_APPROVAL":
            raise HTTPException(status_code=409, detail="Purchase order does not have pending approval")
        request = get_request(db, "PURCHASE_ORDER", purchase_order.id)
        if not request:
            raise HTTPException(status_code=500, detail="Approval workflow not found")
        reject_current_step(
            db,
            request=request,
            user=user,
            comment=data.comment if data else None,
        )
        purchase_order.status = "REJECTED"
        PurchaseOrderService._audit(
            db,
            user,
            purchase_order,
            "REJECT",
            "PENDING_APPROVAL",
            comment=data.comment if data else None,
        )
        db.commit()
        db.refresh(purchase_order)
        return purchase_order

    @staticmethod
    def cancel(db: Session, *, purchase_order_id: int, user):
        purchase_order = db.get(PurchaseOrder, purchase_order_id)
        if not purchase_order:
            raise HTTPException(status_code=404, detail="Purchase order not found")
        if purchase_order.status in {"RECEIVED", "CLOSED", "CANCELLED"}:
            raise HTTPException(status_code=409, detail="Purchase order cannot be cancelled")
        if purchase_order.goods_receipts:
            raise HTTPException(status_code=409, detail="Purchase order with receipts cannot be cancelled")
        previous_status = purchase_order.status
        purchase_order.status = "CANCELLED"
        for requisition in purchase_order.purchase_requisitions:
            if requisition.status == "CONVERTED":
                requisition.status = "APPROVED"
        PurchaseOrderService._audit(db, user, purchase_order, "CANCEL", previous_status)
        db.commit()
        db.refresh(purchase_order)
        return purchase_order