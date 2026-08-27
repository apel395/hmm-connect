from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.dependencies.authorization import is_superuser
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.purchase_requisition import PurchaseRequisition
from app.models.purchase_requisition_item import PurchaseRequisitionItem
from app.models.supplier import Supplier
from app.schemas.approval import ApprovalDecisionRequest
from app.schemas.purchase_order import PurchaseOrderCreate
from app.services.activity_service import AuditService
from app.services.document_number import next_document_number
from app.services.organization_dimensions import validate_dimensions
from app.services.approval import (
    approve_current_step,
    get_request,
    reject_current_step,
    reset_approval,
    start_approval,
)


class PurchaseOrderService:
    @staticmethod
    def _recalculate_totals(purchase_order: PurchaseOrder) -> None:
        subtotal = Decimal("0")
        tax_total = Decimal("0")
        for item in purchase_order.items:
            line_total = Decimal(item.quantity or 0) * Decimal(item.unit_price or 0)
            item.total_price = line_total
            rate = Decimal(item.tax_rate or 0) if item.is_taxable else Decimal("0")
            item.tax_amount = line_total * rate / Decimal("100")
            subtotal += line_total
            tax_total += Decimal(item.tax_amount or 0)
        purchase_order.subtotal = subtotal
        purchase_order.tax_amount = tax_total
        purchase_order.total_amount = subtotal - Decimal(purchase_order.discount_amount or 0) + tax_total

    @staticmethod
    def _validate_positive_costs(purchase_order: PurchaseOrder):
        invalid = [item for item in purchase_order.items if Decimal(item.unit_price or 0) <= 0]
        if not invalid:
            return
        item = invalid[0]
        item_name = item.product.name if item.product else f"item #{item.id}"
        raise HTTPException(
            status_code=409,
            detail=f"Unit price must be greater than zero for {item_name} before this purchase order can continue.",
        )

    @staticmethod
    def _resolve_dimensions(db: Session, data: PurchaseOrderCreate, requisitions: list[PurchaseRequisition]):
        if requisitions:
            resolved = {}
            for field in ("business_unit_id", "department_id", "location_id"):
                values = {
                    getattr(requisition, field)
                    for requisition in requisitions
                    if getattr(requisition, field) is not None
                }
                if len(values) > 1:
                    label = field.removesuffix("_id").replace("_", " ")
                    raise HTTPException(
                        status_code=409,
                        detail=f"Purchase order cannot combine purchase requisitions with different {label} values",
                    )
                resolved[field] = next(iter(values), None)
            business_unit_id = resolved["business_unit_id"]
            department_id = resolved["department_id"]
            location_id = resolved["location_id"]
            validate_dimensions(db, business_unit_id, location_id, department_id, True)
            return business_unit_id, department_id, location_id
        validate_dimensions(db, data.business_unit_id, data.location_id, data.department_id, True)
        if data.department_id is None or data.location_id is None:
            raise HTTPException(status_code=422, detail="Direct purchase orders require department and location")
        return data.business_unit_id, data.department_id, data.location_id

    @staticmethod
    def update(db: Session, *, purchase_order_id: int, data: PurchaseOrderCreate, user):
        purchase_order = (
            db.query(PurchaseOrder)
            .filter(PurchaseOrder.id == purchase_order_id)
            .with_for_update()
            .first()
        )
        if not purchase_order:
            raise HTTPException(status_code=404, detail="Purchase order not found")
        from app.services.document_context import document_context
        context = document_context(db, "PURCHASE_ORDER", purchase_order.id, purchase_order.status, user)
        if not context["allowed_actions"]["can_edit"]:
            raise HTTPException(status_code=409, detail="Purchase order is locked for editing. Reopen it first if you are an administrator.")
        supplier = db.get(Supplier, data.supplier_id)
        if not supplier or not supplier.is_active:
            raise HTTPException(status_code=404, detail="Active supplier not found")

        source_ids = purchase_order.purchase_requisition_ids
        requisitions = (
            db.query(PurchaseRequisition)
            .filter(PurchaseRequisition.id.in_(source_ids))
            .with_for_update()
            .all()
            if source_ids
            else []
        )
        if len(requisitions) != len(set(source_ids)):
            raise HTTPException(status_code=409, detail="Purchase order source requisition no longer exists")

        business_unit_id, department_id, location_id = PurchaseOrderService._resolve_dimensions(
            db, data, requisitions
        )

        source_items = {
            item.id: item
            for requisition in requisitions
            for item in requisition.items
        }
        remaining_by_item = {}
        if requisitions:
            seen_source_ids = set()
            for incoming in data.items:
                source_id = incoming.purchase_requisition_item_id
                if source_id is None or source_id not in source_items:
                    raise HTTPException(status_code=400, detail="Every PO item must belong to its source purchase requisition")
                if source_id in seen_source_ids:
                    raise HTTPException(status_code=400, detail=f"Purchase requisition item {source_id} may appear only once in a PO")
                seen_source_ids.add(source_id)

            for source_id, source_item in source_items.items():
                already_ordered_elsewhere = (
                    db.query(func.coalesce(func.sum(PurchaseOrderItem.quantity), 0))
                    .join(PurchaseOrder)
                    .filter(
                        PurchaseOrderItem.purchase_requisition_item_id == source_id,
                        PurchaseOrderItem.purchase_order_id != purchase_order.id,
                        PurchaseOrder.status != "CANCELLED",
                    )
                    .scalar()
                    or Decimal("0")
                )
                remaining_by_item[source_id] = (
                    source_item,
                    Decimal(source_item.quantity) - Decimal(already_ordered_elsewhere),
                )

        before_total = str(purchase_order.total_amount or 0)
        before_items = [
            {
                "product_id": item.product_id,
                "purchase_requisition_item_id": item.purchase_requisition_item_id,
                "quantity": str(item.quantity),
                "unit_price": str(item.unit_price),
            }
            for item in purchase_order.items
        ]

        purchase_order.supplier_id = data.supplier_id
        purchase_order.order_date = data.order_date or purchase_order.order_date
        purchase_order.expected_date = data.expected_date
        purchase_order.expiry_date = data.expiry_date
        purchase_order.business_unit_id = business_unit_id
        purchase_order.department_id = department_id
        purchase_order.location_id = location_id
        purchase_order.notes = data.notes
        purchase_order.items.clear()

        for incoming in data.items:
            product_id = incoming.product_id
            description = incoming.description
            uom = incoming.uom
            unit_price = incoming.unit_price
            is_taxable = bool(incoming.is_taxable)
            tax_rate = Decimal(incoming.tax_rate or 0)

            if requisitions:
                source_item, remaining = remaining_by_item[incoming.purchase_requisition_item_id]
                if Decimal(incoming.quantity) > remaining:
                    raise HTTPException(
                        status_code=409,
                        detail=f"Quantity exceeds remaining requested quantity for PR item {incoming.purchase_requisition_item_id}",
                    )
                product_id = source_item.product_id
                description = source_item.product.description
                uom = source_item.product.uom
                unit_price = source_item.estimated_price
                is_taxable = bool(source_item.is_taxable)
                tax_rate = Decimal(source_item.tax_rate or 0)

            purchase_order.items.append(PurchaseOrderItem(
                purchase_requisition_item_id=incoming.purchase_requisition_item_id,
                product_id=product_id,
                quantity=incoming.quantity,
                description=description,
                uom=uom,
                received_quantity=Decimal("0"),
                unit_price=unit_price,
                total_price=Decimal("0"),
                is_taxable=is_taxable,
                tax_rate=tax_rate,
                tax_amount=Decimal("0"),
            ))

        PurchaseOrderService._recalculate_totals(purchase_order)
        PurchaseOrderService._audit(
            db,
            user,
            purchase_order,
            "UPDATE",
            edited_during_approval=purchase_order.status == "PENDING_APPROVAL",
            current_approval_level=context.get("current_approval_level"),
            actor_approval_level=context.get("actor_approval_level"),
            before_total=before_total,
            after_total=str(purchase_order.total_amount or 0),
            before_items=before_items,
            business_unit_id=business_unit_id,
            department_id=department_id,
            location_id=location_id,
        )
        db.commit(); db.refresh(purchase_order)
        return purchase_order

    @staticmethod
    def _number(db: Session) -> str:
        return next_document_number(db, "PO")

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
            .with_for_update()
            .all()
        )
        if len(requisitions) != len(set(data.purchase_requisition_ids)):
            raise HTTPException(status_code=404, detail="Purchase requisition not found")
        if any(item.status not in {"APPROVED", "PARTIALLY_CONVERTED"} for item in requisitions):
            raise HTTPException(
                status_code=409,
                detail="Only approved purchase requisitions with remaining quantity can be selected",
            )

        business_unit_id, department_id, location_id = PurchaseOrderService._resolve_dimensions(db, data, requisitions)

        requisition_item_ids = {
            item.id for requisition in requisitions for item in requisition.items
        }
        if requisitions and any(item.purchase_requisition_item_id not in requisition_item_ids for item in data.items):
            raise HTTPException(
                status_code=400,
                detail="PO items must belong to the selected purchase requisitions",
            )
        remaining_by_item = {}
        for requisition in requisitions:
            for requisition_item in requisition.items:
                already_ordered = db.query(func.coalesce(func.sum(PurchaseOrderItem.quantity), 0)).join(PurchaseOrder).filter(
                    PurchaseOrderItem.purchase_requisition_item_id == requisition_item.id,
                    PurchaseOrder.status != "CANCELLED",
                ).scalar() or Decimal("0")
                remaining = Decimal(requisition_item.quantity) - Decimal(already_ordered)
                if remaining > 0:
                    remaining_by_item[requisition_item.id] = (requisition_item, remaining)

        for incoming in data.items:
            if incoming.purchase_requisition_item_id is None:
                continue
            remaining_entry = remaining_by_item.get(incoming.purchase_requisition_item_id)
            if remaining_entry is None:
                raise HTTPException(
                    status_code=409,
                    detail=f"Purchase requisition item {incoming.purchase_requisition_item_id} has no remaining quantity",
                )
            requisition_item, remaining = remaining_entry
            if incoming.quantity > remaining:
                raise HTTPException(status_code=409, detail=f"Quantity exceeds the remaining requested quantity for PR item {incoming.purchase_requisition_item_id}")
            if incoming.product_id is not None and incoming.product_id != requisition_item.product_id:
                raise HTTPException(status_code=400, detail="Product identity must come from the selected purchase requisition")

        purchase_order = PurchaseOrder(
            po_number=PurchaseOrderService._number(db),
            supplier_id=data.supplier_id,
            department_id=department_id,
            location_id=location_id,
            business_unit_id=business_unit_id,
            status="DRAFT",
            order_date=data.order_date or date.today(),
            source_type=data.source_type,
            external_reference=data.external_reference,
            expected_date=data.expected_date,
            expiry_date=data.expiry_date,
            notes=data.notes,
            purchase_requisitions=requisitions,
        )
        for item in data.items:
            product_id = item.product_id
            description = item.description
            uom = item.uom
            unit_price = item.unit_price
            is_taxable = bool(item.is_taxable)
            tax_rate = Decimal(item.tax_rate or 0)
            if item.purchase_requisition_item_id is not None:
                source_item = remaining_by_item[item.purchase_requisition_item_id][0]
                product_id = source_item.product_id
                description = source_item.product.description
                uom = source_item.product.uom
                unit_price = source_item.estimated_price
                is_taxable = bool(source_item.is_taxable)
                tax_rate = Decimal(source_item.tax_rate or 0)
            purchase_order.items.append(
                PurchaseOrderItem(
                    purchase_requisition_item_id=item.purchase_requisition_item_id,
                    product_id=product_id,
                    description=description,
                    uom=uom,
                    quantity=item.quantity,
                    received_quantity=Decimal("0"),
                    unit_price=unit_price,
                    total_price=Decimal("0"),
                    is_taxable=is_taxable,
                    tax_rate=tax_rate,
                    tax_amount=Decimal("0"),
                )
            )
        PurchaseOrderService._recalculate_totals(purchase_order)
        for requisition in requisitions:
            fully_converted = all(
                (db.query(func.coalesce(func.sum(PurchaseOrderItem.quantity), 0)).join(PurchaseOrder).filter(
                    PurchaseOrderItem.purchase_requisition_item_id == item.id,
                    PurchaseOrder.status != "CANCELLED",
                ).scalar() or Decimal("0")) + sum(
                    incoming.quantity for incoming in data.items if incoming.purchase_requisition_item_id == item.id
                ) >= item.quantity
                for item in requisition.items
            )
            requisition.status = "CONVERTED" if fully_converted else "PARTIALLY_CONVERTED"

        db.add(purchase_order)
        db.flush()
        PurchaseOrderService._audit(
            db,
            user,
            purchase_order,
            "CREATE",
            purchase_requisition_ids=data.purchase_requisition_ids,
            business_unit_id=business_unit_id,
            department_id=department_id,
            location_id=location_id,
        )
        db.commit()
        db.refresh(purchase_order)
        return purchase_order

    @staticmethod
    def reopen(db: Session, *, purchase_order_id: int, user):
        if not is_superuser(user):
            raise HTTPException(status_code=403, detail="Only an administrator can reopen a purchase order")
        purchase_order = db.get(PurchaseOrder, purchase_order_id)
        if not purchase_order:
            raise HTTPException(status_code=404, detail="Purchase order not found")
        if purchase_order.status == "DRAFT":
            raise HTTPException(status_code=409, detail="Purchase order is already draft")

        active_receipts = [
            receipt for receipt in purchase_order.goods_receipts
            if receipt.status not in {"RETURNED", "CANCELLED", "VOID"}
        ]
        if active_receipts:
            numbers = ", ".join(receipt.receipt_number for receipt in active_receipts[:5])
            raise HTTPException(
                status_code=409,
                detail=f"Purchase order has active receiving document(s): {numbers}. Return/unwind them before reopening the PO.",
            )

        previous_status = purchase_order.status
        reset_approval(db, "PURCHASE_ORDER", purchase_order.id)
        purchase_order.status = "DRAFT"
        for item in purchase_order.items:
            item.received_quantity = Decimal("0")
        PurchaseOrderService._audit(
            db,
            user,
            purchase_order,
            "REOPEN",
            previous_status,
            admin_override=True,
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
        PurchaseOrderService._validate_positive_costs(purchase_order)
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
        PurchaseOrderService._validate_positive_costs(purchase_order)
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
        db.flush()
        db.refresh(request)
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
        if any(receipt.status not in {"RETURNED", "CANCELLED", "VOID"} for receipt in purchase_order.goods_receipts):
            raise HTTPException(status_code=409, detail="Purchase order with active receipts cannot be cancelled")
        previous_status = purchase_order.status
        purchase_order.status = "CANCELLED"
        for requisition in purchase_order.purchase_requisitions:
            if requisition.status == "CONVERTED":
                requisition.status = "APPROVED"
        PurchaseOrderService._audit(db, user, purchase_order, "CANCEL", previous_status)
        db.commit()
        db.refresh(purchase_order)
        return purchase_order
