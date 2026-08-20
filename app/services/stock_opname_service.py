from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.inventory import Inventory
from app.models.product import Product
from app.models.stock_movement import StockMovement
from app.models.stock_opname import StockOpname, StockOpnameItem
from app.models.user import User
from app.models.warehouse import Warehouse
from app.schemas.approval import ApprovalDecisionRequest
from app.schemas.stock_opname import StockOpnameCountUpdate, StockOpnameCreate
from app.services.activity_service import AuditService
from app.services.approval import approve_current_step, get_request, reject_current_step, start_approval
from app.services.document_number import next_document_number
from app.services.organization_dimensions import validate_dimensions

ZERO = Decimal("0")


class StockOpnameService:
    @staticmethod
    def _get(db: Session, opname_id: int, *, lock: bool = False) -> StockOpname:
        query = db.query(StockOpname).filter(StockOpname.id == opname_id)
        if lock:
            query = query.with_for_update()
        opname = query.first()
        if not opname:
            raise HTTPException(404, "Stock Opname not found")
        return opname

    @staticmethod
    def create(db: Session, *, data: StockOpnameCreate, current_user: User) -> StockOpname:
        warehouse = db.get(Warehouse, data.warehouse_id)
        if not warehouse or not warehouse.is_active:
            raise HTTPException(404, "Active warehouse not found")
        business_unit_id = data.business_unit_id or current_user.default_business_unit_id
        location_id = data.location_id or current_user.default_location_id or current_user.location_id
        department_id = data.department_id or current_user.default_department_id or current_user.department_id
        validate_dimensions(db, business_unit_id, location_id, department_id, True)
        if db.query(StockOpname).filter(StockOpname.warehouse_id == warehouse.id, StockOpname.status.in_(["DRAFT", "PENDING_APPROVAL", "APPROVED"])).first():
            raise HTTPException(409, "Warehouse already has an active Stock Opname")

        opname = StockOpname(opname_number=next_document_number(db, "SO"), status="DRAFT", count_date=data.count_date or date.today(), warehouse_id=warehouse.id, business_unit_id=business_unit_id, location_id=location_id, department_id=department_id, created_by_id=current_user.id, notes=data.notes)
        inventory_rows = db.query(Inventory).filter(Inventory.warehouse_id == warehouse.id).order_by(Inventory.product_id).all()
        for inventory in inventory_rows:
            product = db.get(Product, inventory.product_id)
            if not product or not product.is_active:
                continue
            opname.items.append(StockOpnameItem(product_id=product.id, system_quantity=Decimal(inventory.quantity or 0), unit_cost=Decimal(inventory.average_cost or 0), uom=product.uom))
        db.add(opname); db.flush()
        AuditService.log(db=db, user=current_user, action="CREATE", entity_type="STOCK_OPNAME", entity_id=opname.id, summary=f"Created {opname.opname_number}", document_type="SO", document_number=opname.opname_number, document_status=opname.status)
        db.commit(); db.refresh(opname)
        return opname

    @staticmethod
    def update_counts(db: Session, *, opname_id: int, data: StockOpnameCountUpdate, current_user: User) -> StockOpname:
        opname = StockOpnameService._get(db, opname_id, lock=True)
        if opname.status != "DRAFT":
            raise HTTPException(409, "Only draft Stock Opname can be counted")
        by_id = {item.id: item for item in opname.items}
        seen = set()
        for incoming in data.items:
            if incoming.item_id in seen:
                raise HTTPException(409, f"Duplicate Stock Opname item {incoming.item_id}")
            seen.add(incoming.item_id)
            item = by_id.get(incoming.item_id)
            if not item:
                raise HTTPException(404, f"Stock Opname item {incoming.item_id} not found")
            physical = Decimal(incoming.physical_quantity)
            item.physical_quantity = physical
            item.variance_quantity = physical - Decimal(item.system_quantity)
        if data.notes is not None:
            opname.notes = data.notes
        AuditService.log(db=db, user=current_user, action="COUNT", entity_type="STOCK_OPNAME", entity_id=opname.id, summary=f"Updated physical count {opname.opname_number}", document_type="SO", document_number=opname.opname_number, document_status=opname.status)
        db.commit(); db.refresh(opname)
        return opname

    @staticmethod
    def submit(db: Session, *, opname_id: int, current_user: User) -> StockOpname:
        opname = StockOpnameService._get(db, opname_id, lock=True)
        if opname.status != "DRAFT":
            raise HTTPException(409, "Only draft Stock Opname can be submitted")
        if not opname.items:
            raise HTTPException(409, "Stock Opname has no inventory snapshot")
        missing = [item.product.code for item in opname.items if item.physical_quantity is None]
        if missing:
            raise HTTPException(409, "Physical count is incomplete: " + ", ".join(missing[:10]))
        start_approval(db, entity_type="STOCK_OPNAME", entity_id=opname.id, workflow_code="SO_APPROVAL", user=current_user)
        opname.status = "PENDING_APPROVAL"; opname.submitted_at = datetime.now(timezone.utc)
        AuditService.log(db=db, user=current_user, action="SUBMIT", entity_type="STOCK_OPNAME", entity_id=opname.id, summary=f"Submitted {opname.opname_number}", document_type="SO", document_number=opname.opname_number, document_status=opname.status)
        db.commit(); db.refresh(opname)
        return opname

    @staticmethod
    def approve(db: Session, *, opname_id: int, data: ApprovalDecisionRequest | None, current_user: User) -> StockOpname:
        opname = StockOpnameService._get(db, opname_id, lock=True)
        if opname.status != "PENDING_APPROVAL": raise HTTPException(409, "Stock Opname does not have pending approval")
        approval = get_request(db, "STOCK_OPNAME", opname.id, for_update=True)
        if not approval: raise HTTPException(500, "Approval workflow not found")
        approve_current_step(db, request=approval, user=current_user, comment=data.comment if data else None)
        db.flush(); db.refresh(approval)
        if approval.status == "APPROVED": opname.status = "APPROVED"
        db.commit(); db.refresh(opname)
        return opname

    @staticmethod
    def reject(db: Session, *, opname_id: int, data: ApprovalDecisionRequest | None, current_user: User) -> StockOpname:
        opname = StockOpnameService._get(db, opname_id, lock=True)
        if opname.status != "PENDING_APPROVAL": raise HTTPException(409, "Stock Opname does not have pending approval")
        approval = get_request(db, "STOCK_OPNAME", opname.id, for_update=True)
        if not approval: raise HTTPException(500, "Approval workflow not found")
        reject_current_step(db, request=approval, user=current_user, comment=data.comment if data else None)
        opname.status = "REJECTED"
        db.commit(); db.refresh(opname)
        return opname

    @staticmethod
    def post(db: Session, *, opname_id: int, current_user: User) -> StockOpname:
        opname = StockOpnameService._get(db, opname_id, lock=True)
        if opname.status != "APPROVED":
            raise HTTPException(409, "Only approved Stock Opname can be posted")
        if opname.posted_at is not None:
            raise HTTPException(409, "Stock Opname is already posted")

        prepared = []
        for item in sorted(opname.items, key=lambda row: (row.product_id, row.id)):
            if item.physical_quantity is None:
                raise HTTPException(409, "Stock Opname contains an incomplete physical count")
            inventory = db.query(Inventory).filter(Inventory.warehouse_id == opname.warehouse_id, Inventory.product_id == item.product_id).with_for_update().first()
            if not inventory:
                raise HTTPException(409, f"Inventory row for {item.product.code} no longer exists")
            current_quantity = Decimal(inventory.quantity or 0)
            if current_quantity != Decimal(item.system_quantity):
                raise HTTPException(409, f"Stock changed after snapshot for {item.product.code}; create a new Stock Opname")
            prepared.append((item, inventory))

        for item, inventory in prepared:
            physical = Decimal(item.physical_quantity)
            variance = physical - Decimal(item.system_quantity)
            item.variance_quantity = variance
            inventory.quantity = physical
            if variance != ZERO:
                db.add(StockMovement(product_id=item.product_id, warehouse_id=opname.warehouse_id, business_unit_id=opname.business_unit_id, location_id=opname.location_id, department_id=opname.department_id, movement_type="IN" if variance > 0 else "OUT", quantity=variance, unit_cost=Decimal(item.unit_cost or 0), reference_type="STOCK_OPNAME", reference_id=opname.id, notes=f"Stock Opname adjustment {opname.opname_number}"))

        opname.status = "POSTED"; opname.posted_at = datetime.now(timezone.utc); opname.posted_by_id = current_user.id
        AuditService.log(db=db, user=current_user, action="POST", entity_type="STOCK_OPNAME", entity_id=opname.id, summary=f"Posted {opname.opname_number}", document_type="SO", document_number=opname.opname_number, document_status=opname.status)
        db.commit(); db.refresh(opname)
        return opname
