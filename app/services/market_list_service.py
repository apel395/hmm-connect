from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.market_list import MarketList, MarketListItem
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.supplier import Supplier
from app.models.user import User
from app.schemas.approval import ApprovalDecisionRequest
from app.schemas.market_list import MarketListConvertCreate, MarketListCreate
from app.services.activity_service import AuditService
from app.services.approval import approve_current_step, get_request, reject_current_step, start_approval
from app.services.document_number import next_document_number
from app.services.organization_dimensions import validate_dimensions


MARKET_GROUP_CODES = {"1", "2"}


class MarketListService:
    @staticmethod
    def _product(db: Session, product_id: int) -> Product:
        product = db.get(Product, product_id)
        if not product or not product.is_active:
            raise HTTPException(status_code=404, detail=f"Product {product_id} not found or inactive")
        if str(product.group_code) not in MARKET_GROUP_CODES:
            raise HTTPException(
                status_code=409,
                detail=f"{product.code} - {product.name} is not classified as a market item",
            )
        return product

    @staticmethod
    def _fill_items(db: Session, market_list: MarketList, data: MarketListCreate) -> None:
        if not data.items:
            raise HTTPException(status_code=400, detail="Market List must have items")
        market_list.items.clear()
        for incoming in data.items:
            product = MarketListService._product(db, incoming.product_id)
            subtotal = Decimal(incoming.quantity) * Decimal(incoming.estimated_price)
            taxable = bool(product.is_taxable)
            rate = Decimal(product.tax_rate or 0) if taxable else Decimal("0")
            tax = subtotal * rate / Decimal("100") if taxable else Decimal("0")
            market_list.items.append(
                MarketListItem(
                    product_id=product.id,
                    quantity=incoming.quantity,
                    estimated_price=incoming.estimated_price,
                    total_price=subtotal,
                    is_taxable=taxable,
                    tax_rate=rate,
                    tax_amount=tax,
                )
            )
        market_list.subtotal = sum((Decimal(i.total_price or 0) for i in market_list.items), Decimal("0"))
        market_list.tax_amount = sum((Decimal(i.tax_amount or 0) for i in market_list.items), Decimal("0"))
        market_list.total_amount = market_list.subtotal + market_list.tax_amount

    @staticmethod
    def create(db: Session, *, data: MarketListCreate, current_user: User) -> MarketList:
        market_list = MarketList(
            ml_number=next_document_number(db, "ML"),
            status="DRAFT",
            request_date=data.request_date or date.today(),
            expiry_date=data.expiry_date,
            notes=data.notes,
            source_type=data.source_type,
            external_reference=data.external_reference,
            requested_by_id=current_user.id,
            business_unit_id=data.business_unit_id or current_user.default_business_unit_id,
            location_id=data.location_id or current_user.default_location_id or current_user.location_id,
            department_id=data.department_id or current_user.default_department_id or current_user.department_id,
        )
        validate_dimensions(db, market_list.business_unit_id, market_list.location_id, market_list.department_id, True)
        MarketListService._fill_items(db, market_list, data)
        db.add(market_list)
        db.flush()
        AuditService.log(
            db=db, user=current_user, action="CREATE", entity_type="MARKET_LIST", entity_id=market_list.id,
            summary=f"Created {market_list.ml_number}", document_type="ML", document_number=market_list.ml_number,
            document_status="DRAFT", details={"total_amount": str(market_list.total_amount)},
        )
        db.commit(); db.refresh(market_list)
        return market_list

    @staticmethod
    def update(db: Session, *, market_list_id: int, data: MarketListCreate, current_user: User) -> MarketList:
        market_list = db.get(MarketList, market_list_id)
        if not market_list:
            raise HTTPException(status_code=404, detail="Market List not found")
        from app.services.document_context import document_context
        if not document_context(db, "MARKET_LIST", market_list.id, market_list.status, current_user)["allowed_actions"]["can_edit"]:
            raise HTTPException(status_code=409, detail="Market List is locked for editing")
        market_list.request_date = data.request_date or market_list.request_date
        market_list.expiry_date = data.expiry_date
        market_list.notes = data.notes
        market_list.source_type = data.source_type
        market_list.external_reference = data.external_reference
        market_list.business_unit_id = data.business_unit_id or market_list.business_unit_id
        market_list.location_id = data.location_id or market_list.location_id
        market_list.department_id = data.department_id or market_list.department_id
        validate_dimensions(db, market_list.business_unit_id, market_list.location_id, market_list.department_id, True)
        MarketListService._fill_items(db, market_list, data)
        AuditService.log(
            db=db, user=current_user, action="UPDATE", entity_type="MARKET_LIST", entity_id=market_list.id,
            summary=f"Updated {market_list.ml_number}", document_type="ML", document_number=market_list.ml_number,
            document_status=market_list.status,
        )
        db.commit(); db.refresh(market_list)
        return market_list

    @staticmethod
    def submit(db: Session, *, market_list_id: int, current_user: User) -> MarketList:
        market_list = db.get(MarketList, market_list_id)
        if not market_list:
            raise HTTPException(status_code=404, detail="Market List not found")
        if market_list.status != "DRAFT":
            raise HTTPException(status_code=409, detail="Only draft Market Lists can be submitted")
        if market_list.expiry_date and market_list.expiry_date < date.today():
            market_list.status = "EXPIRED"; db.commit()
            raise HTTPException(status_code=409, detail="Market List has expired")
        if not market_list.items:
            raise HTTPException(status_code=409, detail="Market List must have items")
        unresolved = [i.product.name for i in market_list.items if i.product.tax_category == "REVIEW_REQUIRED"]
        if unresolved:
            raise HTTPException(status_code=409, detail="Finance tax review required before document can continue: " + ", ".join(unresolved[:5]))
        start_approval(db, entity_type="MARKET_LIST", entity_id=market_list.id, workflow_code="ML_APPROVAL", user=current_user)
        market_list.status = "PENDING_APPROVAL"
        AuditService.log(
            db=db, user=current_user, action="SUBMIT", entity_type="MARKET_LIST", entity_id=market_list.id,
            summary=f"Submitted {market_list.ml_number}", document_type="ML", document_number=market_list.ml_number,
            document_status="PENDING_APPROVAL",
        )
        db.commit(); db.refresh(market_list)
        return market_list

    @staticmethod
    def approve(db: Session, *, market_list_id: int, data: ApprovalDecisionRequest | None, current_user: User) -> MarketList:
        market_list = db.get(MarketList, market_list_id)
        if not market_list:
            raise HTTPException(status_code=404, detail="Market List not found")
        if market_list.status != "PENDING_APPROVAL":
            raise HTTPException(status_code=409, detail="Market List does not have pending approval")
        request = get_request(db, "MARKET_LIST", market_list.id, for_update=True)
        if not request:
            raise HTTPException(status_code=500, detail="Approval workflow not found")
        approve_current_step(db, request=request, user=current_user, comment=data.comment if data else None)
        db.flush(); db.refresh(request)
        if request.status == "APPROVED":
            market_list.status = "APPROVED"
        AuditService.log(
            db=db, user=current_user, action="APPROVE", entity_type="MARKET_LIST", entity_id=market_list.id,
            summary=f"Approved {market_list.ml_number}", document_type="ML", document_number=market_list.ml_number,
            document_status=market_list.status, workflow_id=str(request.id), approval_step=request.status,
            details={"comment": data.comment if data else None},
        )
        db.commit(); db.refresh(market_list)
        return market_list

    @staticmethod
    def reject(db: Session, *, market_list_id: int, data: ApprovalDecisionRequest | None, current_user: User) -> MarketList:
        market_list = db.get(MarketList, market_list_id)
        if not market_list:
            raise HTTPException(status_code=404, detail="Market List not found")
        if market_list.status != "PENDING_APPROVAL":
            raise HTTPException(status_code=409, detail="Market List does not have pending approval")
        request = get_request(db, "MARKET_LIST", market_list.id, for_update=True)
        if not request:
            raise HTTPException(status_code=500, detail="Approval workflow not found")
        reject_current_step(db, request=request, user=current_user, comment=data.comment if data else None)
        market_list.status = "REJECTED"
        AuditService.log(
            db=db, user=current_user, action="REJECT", entity_type="MARKET_LIST", entity_id=market_list.id,
            summary=f"Rejected {market_list.ml_number}", document_type="ML", document_number=market_list.ml_number,
            document_status="REJECTED", workflow_id=str(request.id), approval_step="REJECTED",
            details={"comment": data.comment if data else None},
        )
        db.commit(); db.refresh(market_list)
        return market_list

    @staticmethod
    def convert_to_purchase_order(db: Session, *, market_list_id: int, data: MarketListConvertCreate, current_user: User) -> PurchaseOrder:
        market_list = db.query(MarketList).filter(MarketList.id == market_list_id).with_for_update().first()
        if not market_list:
            raise HTTPException(status_code=404, detail="Market List not found")
        if market_list.status != "APPROVED":
            raise HTTPException(status_code=409, detail="Only approved Market Lists can be converted to Purchase Orders")
        supplier = db.get(Supplier, data.supplier_id)
        if not supplier or not supplier.is_active:
            raise HTTPException(status_code=404, detail="Active supplier not found")
        order = PurchaseOrder(
            po_number=next_document_number(db, "PO"), supplier_id=supplier.id, market_list_id=market_list.id,
            status="DRAFT", order_date=date.today(), notes=f"Created from {market_list.ml_number}",
            business_unit_id=market_list.business_unit_id, location_id=market_list.location_id,
            department_id=market_list.department_id, subtotal=market_list.subtotal, tax_amount=market_list.tax_amount,
            total_amount=market_list.total_amount,
        )
        for item in market_list.items:
            order.items.append(PurchaseOrderItem(
                market_list_item_id=item.id, product_id=item.product_id, quantity=item.quantity,
                received_quantity=Decimal("0"), unit_price=item.estimated_price, total_price=item.total_price,
                is_taxable=item.is_taxable, tax_rate=item.tax_rate, tax_amount=item.tax_amount,
                description=item.product.description, uom=item.product.uom,
            ))
        market_list.status = "CONVERTED"
        db.add(order); db.flush()
        AuditService.log(
            db=db, user=current_user, action="CONVERT", entity_type="MARKET_LIST", entity_id=market_list.id,
            summary=f"Converted {market_list.ml_number} to {order.po_number}", document_type="ML",
            document_number=market_list.ml_number, document_status="CONVERTED", reference_document=order.po_number,
        )
        db.commit(); db.refresh(order)
        return order
