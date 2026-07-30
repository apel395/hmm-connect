from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.purchase_requisition import PurchaseRequisition
from app.models.purchase_requisition_item import PurchaseRequisitionItem
from app.models.supplier import Supplier
from app.models.user import User

from app.schemas.approval import ApprovalDecisionRequest
from app.schemas.purchase_requisition import (
    PurchaseRequisitionConvertCreate,
    PurchaseRequisitionCreate,
)

from app.services.activity_service import AuditService
from app.services.approval import (
    approve_current_step,
    get_request,
    reject_current_step,
    start_approval,
)


class PurchaseRequisitionService:

    @staticmethod
    def generate_pr_number(
        db: Session,
    ) -> str:

        count = (
            db.query(PurchaseRequisition)
            .count()
            + 1
        )

        return f"PR-{count:06d}"

    @staticmethod
    def create(
        db: Session,
        *,
        data: PurchaseRequisitionCreate,
        current_user: User,
    ) -> PurchaseRequisition:

        if not data.items:
            raise HTTPException(
                status_code=400,
                detail="Purchase requisition must have items",
            )

        purchase_requisition = PurchaseRequisition(
            pr_number=PurchaseRequisitionService.generate_pr_number(
                db
            ),
            status="DRAFT",
            notes=data.notes,
            expiry_date=data.expiry_date,
            total_amount=Decimal("0"),
        )

        total_amount = Decimal("0")

        for item_data in data.items:

            product = (
                db.query(Product)
                .filter(
                    Product.id == item_data.product_id
                )
                .first()
            )

            if not product:
                raise HTTPException(
                    status_code=404,
                    detail="Product not found",
                )

            total_price = (
                item_data.quantity
                * item_data.estimated_price
            )

            purchase_requisition.items.append(
                PurchaseRequisitionItem(
                    product_id=item_data.product_id,
                    quantity=item_data.quantity,
                    estimated_price=item_data.estimated_price,
                    total_price=total_price,
                )
            )

            total_amount += total_price

        purchase_requisition.total_amount = total_amount

        db.add(
            purchase_requisition
        )

        db.commit()

        db.refresh(
            purchase_requisition
        )

        AuditService.log(
            db=db,
            user=current_user,
            action="CREATE",
            entity_type="PURCHASE_REQUISITION",
            entity_id=purchase_requisition.id,
            summary=(
                f"Created "
                f"{purchase_requisition.pr_number}"
            ),
            document_type="PR",
            document_number=purchase_requisition.pr_number,
            document_status="DRAFT",
            details={
                "total_amount": str(total_amount),
            },
        )

        db.commit()

        return purchase_requisition

    @staticmethod
    def submit(
        db: Session,
        *,
        purchase_requisition_id: int,
        current_user: User,
    ) -> PurchaseRequisition:

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

        if (
            purchase_requisition.expiry_date
            and purchase_requisition.expiry_date < date.today()
        ):
            purchase_requisition.status = "EXPIRED"
            AuditService.log(
                db=db,
                user=current_user,
                action="EXPIRE",
                entity_type="PURCHASE_REQUISITION",
                entity_id=purchase_requisition.id,
                summary=f"Expired {purchase_requisition.pr_number}",
                document_type="PR",
                document_number=purchase_requisition.pr_number,
                document_status="EXPIRED",
            )
            db.commit()
            raise HTTPException(
                status_code=409,
                detail="Purchase requisition has expired",
            )

        if purchase_requisition.status != "DRAFT":
            raise HTTPException(
                status_code=400,
                detail=(
                    "Only draft purchase "
                    "requisitions can be "
                    "submitted"
                ),
            )

        if not purchase_requisition.items:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Purchase requisition "
                    "must have items"
                ),
            )

        start_approval(
            db,
            entity_type="PURCHASE_REQUISITION",
            entity_id=purchase_requisition.id,
            workflow_code="PR_APPROVAL",
            user=current_user,
        )

        purchase_requisition.status = (
            "PENDING_APPROVAL"
        )

        AuditService.log(
            db=db,
            user=current_user,
            action="SUBMIT",
            entity_type="PURCHASE_REQUISITION",
            entity_id=purchase_requisition.id,
            summary=(
                f"Submitted "
                f"{purchase_requisition.pr_number}"
            ),
            document_type="PR",
            document_number=purchase_requisition.pr_number,
            document_status="PENDING_APPROVAL",
        )

        db.commit()

        db.refresh(
            purchase_requisition
        )

        return purchase_requisition

    @staticmethod
    def approve(
        db: Session,
        *,
        purchase_requisition_id: int,
        data: ApprovalDecisionRequest | None,
        current_user: User,
    ) -> PurchaseRequisition:

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

        if (
            purchase_requisition.status
            != "PENDING_APPROVAL"
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Purchase requisition "
                    "does not have pending "
                    "approval"
                ),
            )

        request = get_request(
            db,
            "PURCHASE_REQUISITION",
            purchase_requisition.id,
        )

        if not request:
            raise HTTPException(
                status_code=500,
                detail="Approval workflow not found",
            )

        approve_current_step(
            db,
            request=request,
            user=current_user,
            comment=(
                data.comment
                if data
                else None
            ),
        )

        if request.status == "APPROVED":

            purchase_requisition.status = (
                "APPROVED"
            )

        AuditService.log(
            db=db,
            user=current_user,
            action="APPROVE",
            entity_type="PURCHASE_REQUISITION",
            entity_id=purchase_requisition.id,
            summary=(
                f"Approved "
                f"{purchase_requisition.pr_number}"
            ),
            document_type="PR",
            document_number=(
                purchase_requisition.pr_number
            ),
            document_status=(
                purchase_requisition.status
            ),
            workflow_id=str(request.id),
            approval_level=(
                request.current_step_order
            ),
            approval_step=request.status,
            details={
                "comment": (
                    data.comment
                    if data
                    else None
                ),
            },
        )

        db.commit()

        db.refresh(
            purchase_requisition
        )

        return purchase_requisition

    @staticmethod
    def reject(
        db: Session,
        *,
        purchase_requisition_id: int,
        data: ApprovalDecisionRequest | None,
        current_user: User,
    ) -> PurchaseRequisition:

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

        if (
            purchase_requisition.status
            != "PENDING_APPROVAL"
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Purchase requisition "
                    "does not have pending "
                    "approval"
                ),
            )

        request = get_request(
            db,
            "PURCHASE_REQUISITION",
            purchase_requisition.id,
        )

        if not request:
            raise HTTPException(
                status_code=500,
                detail="Approval workflow not found",
            )

        reject_current_step(
            db,
            request=request,
            user=current_user,
            comment=(
                data.comment
                if data
                else None
            ),
        )

        purchase_requisition.status = (
            "REJECTED"
        )

        AuditService.log(
            db=db,
            user=current_user,
            action="REJECT",
            entity_type="PURCHASE_REQUISITION",
            entity_id=purchase_requisition.id,
            summary=(
                f"Rejected "
                f"{purchase_requisition.pr_number}"
            ),
            document_type="PR",
            document_number=(
                purchase_requisition.pr_number
            ),
            document_status="REJECTED",
            workflow_id=str(request.id),
            approval_step="REJECTED",
            details={
                "comment": (
                    data.comment
                    if data
                    else None
                ),
            },
        )

        db.commit()

        db.refresh(
            purchase_requisition
        )

        return purchase_requisition

    @staticmethod
    def generate_po_number(
        db: Session,
    ) -> str:

        count = (
            db.query(PurchaseOrder)
            .count()
            + 1
        )

        return f"PO-{count:06d}"

    @staticmethod
    def convert_to_purchase_order(
        db: Session,
        *,
        purchase_requisition_id: int,
        data: PurchaseRequisitionConvertCreate,
        current_user: User,
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
                detail=(
                    "Purchase requisition "
                    "not found"
                ),
            )

        if purchase_requisition.status != "APPROVED":
            raise HTTPException(
                status_code=400,
                detail=(
                    "Only approved purchase "
                    "requisitions can be "
                    "converted to purchase orders"
                ),
            )

        supplier = (
            db.query(Supplier)
            .filter(
                Supplier.id
                == data.supplier_id
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
                    "Purchase requisition "
                    "must have at least one item"
                ),
            )

        purchase_order = PurchaseOrder(
            po_number=(
                PurchaseRequisitionService.generate_po_number(
                    db
                )
            ),
            supplier_id=data.supplier_id,
            status="DRAFT",
            total_amount=Decimal("0"),
            notes=(
                f"Created from "
                f"{purchase_requisition.pr_number}"
            ),
            purchase_requisitions=[
                purchase_requisition
            ],
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

        purchase_order.total_amount = (
            total_amount
        )

        purchase_requisition.status = (
            "CONVERTED"
        )

        db.add(
            purchase_order
        )

        db.flush()

        AuditService.log(
            db=db,
            user=current_user,
            action="CONVERT",
            entity_type="PURCHASE_REQUISITION",
            entity_id=purchase_requisition.id,
            summary=(
                f"Converted "
                f"{purchase_requisition.pr_number} "
                f"to "
                f"{purchase_order.po_number}"
            ),
            document_type="PR",
            document_number=(
                purchase_requisition.pr_number
            ),
            document_status="CONVERTED",
            reference_document=(
                purchase_order.po_number
            ),
            details={
                "purchase_order_id":
                    purchase_order.id,
            },
        )

        AuditService.log(
            db=db,
            user=current_user,
            action="CREATE",
            entity_type="PURCHASE_ORDER",
            entity_id=purchase_order.id,
            summary=(
                f"Created Purchase Order "
                f"{purchase_order.po_number}"
            ),
            document_type="PO",
            document_number=(
                purchase_order.po_number
            ),
            document_status=(
                purchase_order.status
            ),
            reference_document=(
                purchase_requisition.pr_number
            ),
            details={
                "supplier_id":
                    purchase_order.supplier_id,
                "total_amount":
                    str(
                        purchase_order.total_amount
                    ),
            },
        )

        db.commit()

        db.refresh(
            purchase_order
        )

        return {
            "message": (
                "Purchase requisition "
                "converted to purchase order"
            ),
            "purchase_requisition_id":
                purchase_requisition.id,
            "purchase_order_id":
                purchase_order.id,
            "po_number":
                purchase_order.po_number,
            "status":
                purchase_order.status,
        }