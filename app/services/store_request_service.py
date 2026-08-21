from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.inventory import Inventory
from app.models.product import Product
from app.models.stock_movement import StockMovement
from app.models.store_request import StoreIssue, StoreIssueItem, StoreRequest, StoreRequestItem
from app.models.user import User
from app.models.warehouse import Warehouse
from app.schemas.approval import ApprovalDecisionRequest
from app.schemas.store_request import StoreRequestCreate, StoreRequestIssueCreate
from app.services.activity_service import AuditService
from app.services.approval import approve_current_step, get_request, reject_current_step, start_approval
from app.services.document_number import next_document_number
from app.services.organization_dimensions import validate_dimensions


class StoreRequestService:
    @staticmethod
    def _product(db: Session, product_id: int) -> Product:
        product = db.get(Product, product_id)
        if not product or not product.is_active:
            raise HTTPException(status_code=404, detail=f"Product {product_id} not found or inactive")
        return product

    @staticmethod
    def _warehouse(db: Session, warehouse_id: int) -> Warehouse:
        warehouse = db.get(Warehouse, warehouse_id)
        if not warehouse or not warehouse.is_active:
            raise HTTPException(status_code=404, detail="Active warehouse not found")
        return warehouse

    @staticmethod
    def _fill_items(db: Session, request: StoreRequest, data: StoreRequestCreate) -> None:
        if not data.items:
            raise HTTPException(status_code=400, detail="Store Request must have items")
        request.items.clear()
        seen: set[int] = set()
        for incoming in data.items:
            if incoming.product_id in seen:
                raise HTTPException(status_code=409, detail=f"Duplicate product {incoming.product_id} in Store Request")
            seen.add(incoming.product_id)
            product = StoreRequestService._product(db, incoming.product_id)
            request.items.append(
                StoreRequestItem(
                    product_id=product.id,
                    requested_quantity=Decimal(incoming.quantity),
                    issued_quantity=Decimal("0"),
                    uom=product.uom,
                )
            )

    @staticmethod
    def _validate_available_stock(db: Session, request: StoreRequest) -> None:
        inventory = {
            row.product_id: Decimal(row.quantity or 0)
            for row in db.query(Inventory).filter(Inventory.warehouse_id == request.warehouse_id).all()
        }
        shortages = []
        for item in request.items:
            requested = Decimal(item.requested_quantity or 0)
            available = inventory.get(item.product_id, Decimal("0"))
            if requested > available:
                shortages.append(f"{item.product.name}: available {available}, requested {requested}")
        if shortages:
            raise HTTPException(
                status_code=409,
                detail="Warehouse stock is insufficient: " + "; ".join(shortages),
            )

    @staticmethod
    def create(db: Session, *, data: StoreRequestCreate, current_user: User) -> StoreRequest:
        StoreRequestService._warehouse(db, data.warehouse_id)
        business_unit_id = data.business_unit_id or current_user.default_business_unit_id
        location_id = data.location_id or current_user.default_location_id or current_user.location_id
        department_id = data.department_id or current_user.default_department_id or current_user.department_id
        validate_dimensions(db, business_unit_id, location_id, department_id, True)
        request = StoreRequest(
            sr_number=next_document_number(db, "SR"),
            status="DRAFT",
            request_date=data.request_date or date.today(),
            notes=data.notes,
            business_unit_id=business_unit_id,
            department_id=department_id,
            location_id=location_id,
            warehouse_id=data.warehouse_id,
            requested_by_id=current_user.id,
        )
        StoreRequestService._fill_items(db, request, data)
        StoreRequestService._validate_available_stock(db, request)
        db.add(request)
        db.flush()
        AuditService.log(
            db=db, user=current_user, action="CREATE", entity_type="STORE_REQUEST", entity_id=request.id,
            summary=f"Created {request.sr_number}", document_type="SR", document_number=request.sr_number,
            document_status="DRAFT",
        )
        db.commit(); db.refresh(request)
        return request

    @staticmethod
    def update(db: Session, *, request_id: int, data: StoreRequestCreate, current_user: User) -> StoreRequest:
        request = db.get(StoreRequest, request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Store Request not found")
        if request.status != "DRAFT":
            raise HTTPException(status_code=409, detail="Only draft Store Requests can be edited")
        StoreRequestService._warehouse(db, data.warehouse_id)
        request.request_date = data.request_date or request.request_date
        request.notes = data.notes
        request.business_unit_id = data.business_unit_id or request.business_unit_id
        request.location_id = data.location_id or request.location_id
        request.department_id = data.department_id or request.department_id
        request.warehouse_id = data.warehouse_id
        validate_dimensions(db, request.business_unit_id, request.location_id, request.department_id, True)
        StoreRequestService._fill_items(db, request, data)
        StoreRequestService._validate_available_stock(db, request)
        AuditService.log(
            db=db, user=current_user, action="UPDATE", entity_type="STORE_REQUEST", entity_id=request.id,
            summary=f"Updated {request.sr_number}", document_type="SR", document_number=request.sr_number,
            document_status=request.status,
        )
        db.commit(); db.refresh(request)
        return request

    @staticmethod
    def submit(db: Session, *, request_id: int, current_user: User) -> StoreRequest:
        request = db.get(StoreRequest, request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Store Request not found")
        if request.status != "DRAFT":
            raise HTTPException(status_code=409, detail="Only draft Store Requests can be submitted")
        if not request.items:
            raise HTTPException(status_code=409, detail="Store Request must have items")
        StoreRequestService._warehouse(db, request.warehouse_id)
        StoreRequestService._validate_available_stock(db, request)
        start_approval(db, entity_type="STORE_REQUEST", entity_id=request.id, workflow_code="SR_APPROVAL", user=current_user)
        request.status = "PENDING_APPROVAL"
        AuditService.log(
            db=db, user=current_user, action="SUBMIT", entity_type="STORE_REQUEST", entity_id=request.id,
            summary=f"Submitted {request.sr_number}", document_type="SR", document_number=request.sr_number,
            document_status=request.status,
        )
        db.commit(); db.refresh(request)
        return request

    @staticmethod
    def approve(db: Session, *, request_id: int, data: ApprovalDecisionRequest | None, current_user: User) -> StoreRequest:
        request = db.get(StoreRequest, request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Store Request not found")
        if request.status != "PENDING_APPROVAL":
            raise HTTPException(status_code=409, detail="Store Request does not have pending approval")
        StoreRequestService._validate_available_stock(db, request)
        approval = get_request(db, "STORE_REQUEST", request.id, for_update=True)
        if not approval:
            raise HTTPException(status_code=500, detail="Approval workflow not found")
        approve_current_step(db, request=approval, user=current_user, comment=data.comment if data else None)
        db.flush(); db.refresh(approval)
        if approval.status == "APPROVED":
            request.status = "APPROVED"
        AuditService.log(
            db=db, user=current_user, action="APPROVE", entity_type="STORE_REQUEST", entity_id=request.id,
            summary=f"Approved {request.sr_number}", document_type="SR", document_number=request.sr_number,
            document_status=request.status, workflow_id=str(approval.id), approval_step=approval.status,
            details={"comment": data.comment if data else None},
        )
        db.commit(); db.refresh(request)
        return request

    @staticmethod
    def reject(db: Session, *, request_id: int, data: ApprovalDecisionRequest | None, current_user: User) -> StoreRequest:
        request = db.get(StoreRequest, request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Store Request not found")
        if request.status != "PENDING_APPROVAL":
            raise HTTPException(status_code=409, detail="Store Request does not have pending approval")
        approval = get_request(db, "STORE_REQUEST", request.id, for_update=True)
        if not approval:
            raise HTTPException(status_code=500, detail="Approval workflow not found")
        reject_current_step(db, request=approval, user=current_user, comment=data.comment if data else None)
        request.status = "REJECTED"
        AuditService.log(
            db=db, user=current_user, action="REJECT", entity_type="STORE_REQUEST", entity_id=request.id,
            summary=f"Rejected {request.sr_number}", document_type="SR", document_number=request.sr_number,
            document_status=request.status, workflow_id=str(approval.id), approval_step="REJECTED",
            details={"comment": data.comment if data else None},
        )
        db.commit(); db.refresh(request)
        return request

    @staticmethod
    def create_issue(db: Session, *, request_id: int, data: StoreRequestIssueCreate, current_user: User) -> StoreIssue:
        request = db.query(StoreRequest).filter(StoreRequest.id == request_id).with_for_update().first()
        if not request:
            raise HTTPException(status_code=404, detail="Store Request not found")
        if request.status not in {"APPROVED", "PARTIALLY_ISSUED"}:
            raise HTTPException(status_code=409, detail="Only approved Store Requests can issue goods")
        if db.query(StoreIssue).filter(StoreIssue.store_request_id == request.id, StoreIssue.status == "DRAFT").first():
            raise HTTPException(status_code=409, detail="Store Request already has an active issue draft")
        if not data.items:
            raise HTTPException(status_code=400, detail="Issue must have items")
        requested = {item.id: item for item in request.items}
        issue = StoreIssue(
            issue_number=next_document_number(db, "SI"),
            store_request_id=request.id,
            status="DRAFT",
            notes=data.notes,
            created_by_id=current_user.id,
        )
        seen: set[int] = set()
        for incoming in data.items:
            if incoming.item_id in seen:
                raise HTTPException(status_code=409, detail=f"Duplicate Store Request item {incoming.item_id}")
            seen.add(incoming.item_id)
            source = requested.get(incoming.item_id)
            if not source:
                raise HTTPException(status_code=404, detail=f"Store Request item {incoming.item_id} not found")
            remaining = Decimal(source.requested_quantity) - Decimal(source.issued_quantity or 0)
            qty = Decimal(incoming.quantity)
            if qty > remaining:
                raise HTTPException(status_code=409, detail=f"Issue quantity exceeds remaining quantity for {source.product.name}")
            issue.items.append(StoreIssueItem(
                store_request_item_id=source.id,
                product_id=source.product_id,
                quantity=qty,
            ))
        db.add(issue)
        db.flush()
        AuditService.log(
            db=db, user=current_user, action="CREATE_ISSUE", entity_type="STORE_REQUEST", entity_id=request.id,
            summary=f"Created issue {issue.issue_number} for {request.sr_number}", document_type="SR",
            document_number=request.sr_number, document_status=request.status, reference_document=issue.issue_number,
        )
        db.commit(); db.refresh(issue)
        return issue

    @staticmethod
    def post_issue(db: Session, *, issue_id: int, current_user: User) -> StoreIssue:
        issue = db.query(StoreIssue).filter(StoreIssue.id == issue_id).with_for_update().first()
        if not issue:
            raise HTTPException(status_code=404, detail="Store Issue not found")
        if issue.status != "DRAFT":
            raise HTTPException(status_code=409, detail="Store Issue is already posted")
        request = db.query(StoreRequest).filter(StoreRequest.id == issue.store_request_id).with_for_update().one()
        if request.status not in {"APPROVED", "PARTIALLY_ISSUED"}:
            raise HTTPException(status_code=409, detail="Store Request is not eligible for issue posting")
        if not issue.items:
            raise HTTPException(status_code=409, detail="Store Issue has no items")

        source_items = {item.id: item for item in request.items}
        prepared_lines = []
        # Lock and validate every line before changing stock. Sorting inventory
        # locks also gives concurrent multi-line issues a deterministic order.
        for line in sorted(issue.items, key=lambda item: (item.product_id, item.id)):
            source = source_items.get(line.store_request_item_id)
            if not source:
                raise HTTPException(status_code=409, detail="Store Request item no longer exists")
            remaining = Decimal(source.requested_quantity) - Decimal(source.issued_quantity or 0)
            qty = Decimal(line.quantity)
            if qty <= 0 or qty > remaining:
                raise HTTPException(status_code=409, detail=f"Invalid remaining quantity for {source.product.name}")
            inventory = (
                db.query(Inventory)
                .filter(Inventory.product_id == source.product_id, Inventory.warehouse_id == request.warehouse_id)
                .with_for_update()
                .first()
            )
            if not inventory or Decimal(inventory.quantity or 0) < qty:
                available = Decimal(inventory.quantity or 0) if inventory else Decimal("0")
                raise HTTPException(
                    status_code=409,
                    detail=f"Insufficient stock for {source.product.name}: available {available}, requested {qty}",
                )
            unit_cost = Decimal(inventory.average_cost or 0)
            prepared_lines.append((source, inventory, qty, unit_cost))

        for source, inventory, qty, unit_cost in prepared_lines:
            inventory.quantity = Decimal(inventory.quantity or 0) - qty
            source.issued_quantity = Decimal(source.issued_quantity or 0) + qty
            db.add(StockMovement(
                product_id=source.product_id,
                warehouse_id=request.warehouse_id,
                business_unit_id=request.business_unit_id,
                department_id=request.department_id,
                location_id=request.location_id,
                movement_type="OUT",
                quantity=-qty,
                unit_cost=unit_cost,
                reference_type="STORE_REQUEST",
                reference_id=request.id,
                notes=f"{request.sr_number} / {issue.issue_number}",
            ))

        complete = all(Decimal(item.issued_quantity or 0) >= Decimal(item.requested_quantity) for item in request.items)
        request.status = "ISSUED" if complete else "PARTIALLY_ISSUED"
        issue.status = "POSTED"
        issue.posted_by_id = current_user.id
        issue.posted_at = datetime.now(timezone.utc)
        AuditService.log(
            db=db, user=current_user, action="POST_ISSUE", entity_type="STORE_REQUEST", entity_id=request.id,
            summary=f"Posted issue {issue.issue_number} for {request.sr_number}", document_type="SR",
            document_number=request.sr_number, document_status=request.status, reference_document=issue.issue_number,
        )
        db.commit(); db.refresh(issue)
        return issue
