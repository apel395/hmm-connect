from app.services.inventory_posting import post_inventory_journal
from app.services.fiscal_period_service import FiscalPeriodService
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.inventory import Inventory
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
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
from app.services.direct_coa_service import DirectCoaService
from app.services.organization_dimensions import validate_dimensions
from app.services.location_access import enforce_location_access, enforce_warehouse_access, resolve_location_id


class StoreRequestService:
    @staticmethod
    def _product(db: Session, product_id: int) -> Product:
        product = db.get(Product, product_id)
        if not product or not product.is_active:
            raise HTTPException(status_code=404, detail=f"Product {product_id} not found or inactive")
        return product

    @staticmethod
    def _warehouse(db: Session, warehouse_id: int, current_user: User, location_id: int | None = None) -> Warehouse:
        warehouse = db.get(Warehouse, warehouse_id)
        if not warehouse or not warehouse.is_active:
            raise HTTPException(status_code=404, detail="Active warehouse not found")
        enforce_warehouse_access(current_user, warehouse)
        if location_id is not None and warehouse.location_id != location_id:
            raise HTTPException(status_code=422, detail="Warehouse must belong to the Store Request location")
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
    def _assert_request_integrity(db: Session, request: StoreRequest, current_user: User) -> Warehouse:
        if not request.items:
            raise HTTPException(409, "Store Request must contain at least one item")
        for item in request.items:
            if Decimal(item.requested_quantity or 0) <= 0:
                raise HTTPException(
                    409,
                    f"Store Request item {item.id or item.product_id} must have positive quantity",
                )
        return StoreRequestService._warehouse(
            db,
            request.warehouse_id,
            current_user,
            request.location_id,
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
                product = db.get(Product, item.product_id)
                name = product.name if product else f"Product {item.product_id}"
                shortages.append(f"{name}: available {available}, requested {requested}")
        if shortages:
            raise HTTPException(
                status_code=409,
                detail="Warehouse stock is insufficient: " + "; ".join(shortages),
            )

    @staticmethod
    def create(db: Session, *, data: StoreRequestCreate, current_user: User) -> StoreRequest:
        location_id = resolve_location_id(current_user, data.location_id)
        warehouse = StoreRequestService._warehouse(db, data.warehouse_id, current_user, location_id)
        location = warehouse.location
        if location is None or location.business_unit_id is None:
            raise HTTPException(409, "Store Request warehouse Location must belong to a Business Unit")
        business_unit_id = location.business_unit_id
        department_id = data.department_id or current_user.default_department_id or current_user.department_id
        validate_dimensions(db, business_unit_id, location_id, department_id, True)
        FiscalPeriodService.validate_posting_date(db, data.request_date or FiscalPeriodService.business_today())
        request = StoreRequest(
            sr_number=next_document_number(db, "SR"),
            status="DRAFT",
            request_date=data.request_date or FiscalPeriodService.business_today(),
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
        enforce_location_access(current_user, request.location_id)
        if request.status != "DRAFT":
            raise HTTPException(status_code=409, detail="Only draft Store Requests can be edited")
        location_id = resolve_location_id(current_user, data.location_id or request.location_id)
        warehouse = StoreRequestService._warehouse(db, data.warehouse_id, current_user, location_id)
        if warehouse.location is None or warehouse.location.business_unit_id is None:
            raise HTTPException(409, "Store Request warehouse Location must belong to a Business Unit")
        if data.request_date and data.request_date != request.request_date:
            FiscalPeriodService.validate_posting_date(db, data.request_date)
        request.request_date = data.request_date or request.request_date
        request.notes = data.notes
        request.business_unit_id = warehouse.location.business_unit_id
        request.location_id = location_id
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
        enforce_location_access(current_user, request.location_id)
        if request.status != "DRAFT":
            raise HTTPException(status_code=409, detail="Only draft Store Requests can be submitted")
        StoreRequestService._assert_request_integrity(db, request, current_user)
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
        enforce_location_access(current_user, request.location_id)
        if request.status != "PENDING_APPROVAL":
            raise HTTPException(status_code=409, detail="Store Request does not have pending approval")
        StoreRequestService._assert_request_integrity(db, request, current_user)
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
        enforce_location_access(current_user, request.location_id)
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
        enforce_location_access(current_user, request.location_id)
        if request.status not in {"APPROVED", "PARTIALLY_ISSUED"}:
            raise HTTPException(status_code=409, detail="Only approved Store Requests can issue goods")
        StoreRequestService._assert_request_integrity(db, request, current_user)
        if db.query(StoreIssue).filter(StoreIssue.store_request_id == request.id, StoreIssue.status == "DRAFT").first():
            raise HTTPException(status_code=409, detail="Store Request already has an active issue draft")
        if not data.items:
            raise HTTPException(status_code=400, detail="Issue must have items")
        issue_date = data.issue_date or FiscalPeriodService.business_today()
        FiscalPeriodService.validate_posting_date(db, issue_date)
        if issue_date < request.request_date:
            raise HTTPException(status_code=400, detail="Issue date cannot precede request date")
        requested = {item.id: item for item in request.items}
        issue = StoreIssue(
            issue_number=next_document_number(db, "SI"),
            store_request_id=request.id,
            status="DRAFT",
            issue_date=issue_date,
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
            if qty <= 0:
                raise HTTPException(status_code=409, detail=f"Issue quantity must be positive for {source.product.name}")
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
        enforce_location_access(current_user, request.location_id)
        if request.status not in {"APPROVED", "PARTIALLY_ISSUED"}:
            raise HTTPException(status_code=409, detail="Store Request is not eligible for issue posting")
        if not issue.items:
            raise HTTPException(status_code=409, detail="Store Issue has no items")

        issue_date = issue.issue_date or FiscalPeriodService.business_today()
        if issue_date < request.request_date:
            raise HTTPException(422, "Issue date cannot precede request date")
        FiscalPeriodService.validate_posting_date(db, issue_date)
        issue.issue_date = issue_date
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
            if unit_cost <= 0:
                raise HTTPException(status_code=409, detail=f"Item {source.product.name} has no positive inventory cost")
            resolver = DirectCoaService(db)
            inventory_account = resolver.inventory_account(source.product)
            cogs_account = resolver.cogs_account(source.product)
            prepared_lines.append((source, inventory, qty, unit_cost, inventory_account, cogs_account))

        grouped = {}
        for source, _inventory, qty, unit_cost, inventory_account, cogs_account in prepared_lines:
            amount = qty * unit_cost
            key = (inventory_account.id, cogs_account.id)
            grouped[key] = grouped.get(key, Decimal("0")) + amount

        journal = JournalEntry(
            journal_number=next_document_number(db, "JV", digits=4),
            posting_date=issue_date,
            status="DRAFT",
            document_type="STORE_ISSUE",
            document_number=issue.issue_number,
            reference_type="STORE_ISSUE",
            reference_id=issue.id,
            description=f"Inventory consumption {issue.issue_number}",
            created_by_id=current_user.id,
            business_unit_id=request.business_unit_id,
            location_id=request.location_id,
            department_id=request.department_id,
        )
        line_number = 1
        for (inventory_account_id, cogs_account_id), amount in grouped.items():
            journal.lines.append(JournalLine(
                line_number=line_number, account_id=cogs_account_id, debit=amount, credit=0,
                description=f"Consumption {issue.issue_number}", business_unit_id=request.business_unit_id,
                location_id=request.location_id, department_id=request.department_id,
            ))
            line_number += 1
            journal.lines.append(JournalLine(
                line_number=line_number, account_id=inventory_account_id, debit=0, credit=amount,
                description=f"Inventory issued {issue.issue_number}", business_unit_id=request.business_unit_id,
                location_id=request.location_id, department_id=request.department_id,
            ))
            line_number += 1
        db.add(journal)
        db.flush()
        post_inventory_journal(db, journal, current_user)

        for source, inventory, qty, unit_cost, inventory_account, cogs_account in prepared_lines:
            inventory.quantity = Decimal(inventory.quantity or 0) - qty
            source.issued_quantity = Decimal(source.issued_quantity or 0) + qty
            db.add(StockMovement(
                product_id=source.product_id,
                warehouse_id=request.warehouse_id,
                business_unit_id=request.business_unit_id,
                department_id=request.department_id,
                location_id=request.location_id,
                movement_type="OUT",
                created_at=datetime.combine(issue_date, datetime.min.time(), tzinfo=timezone.utc),
                quantity=-qty,
                unit_cost=unit_cost,
                reference_type="STORE_REQUEST",
                reference_id=request.id,
                notes=f"{request.sr_number} / {issue.issue_number}",
                inventory_account_id=inventory_account.id,
                offset_account_id=cogs_account.id,
                journal_entry_id=journal.id,
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
