from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.inventory import Inventory
from app.models.location import Location
from app.models.product import Product
from app.models.stock_movement import StockMovement
from app.models.stock_opname import StockOpname, StockOpnameItem
from app.models.user import User
from app.models.warehouse import Warehouse
from app.schemas.approval import ApprovalDecisionRequest
from app.schemas.stock_opname import StockOpnameCountUpdate, StockOpnameCreate
from app.services.activity_service import AuditService
from app.services.approval import (
    approve_current_step,
    get_request,
    reject_current_step,
    reset_approval,
    start_approval,
)
from app.services.document_number import next_document_number
from app.services.organization_dimensions import validate_dimensions

ZERO = Decimal("0")


class StockOpnameService:
    @staticmethod
    def _get(db: Session, opname_id: int, *, lock: bool = False) -> StockOpname:
        q = db.query(StockOpname).filter(StockOpname.id == opname_id)
        q = q.with_for_update() if lock else q
        row = q.first()
        if not row:
            raise HTTPException(404, "Stock Opname not found")
        return row

    @staticmethod
    def _resolve_dimensions(
        db: Session, *, data: StockOpnameCreate, current_user: User
    ) -> tuple[int, int, int | None]:
        location_id = (
            data.location_id
            or current_user.default_location_id
            or current_user.location_id
        )
        if not location_id:
            raise HTTPException(422, "Location is required for Stock Opname")

        location = db.get(Location, location_id)
        if not location or not location.is_active:
            raise HTTPException(422, "Active Location is required for Stock Opname")

        # Location is the authoritative operational dimension.
        business_unit_id = location.business_unit_id
        if not business_unit_id:
            raise HTTPException(
                422, "Selected Location is not assigned to a Business Unit"
            )

        department_id = (
            data.department_id
            or current_user.default_department_id
            or current_user.department_id
        )

        validate_dimensions(
            db,
            business_unit_id,
            location_id,
            department_id,
            True,
        )
        return business_unit_id, location_id, department_id

    @staticmethod
    def create(
        db: Session, *, data: StockOpnameCreate, current_user: User
    ) -> StockOpname:
        wh = db.get(Warehouse, data.warehouse_id)
        if not wh or not wh.is_active:
            raise HTTPException(404, "Active warehouse not found")

        bu, loc, dep = StockOpnameService._resolve_dimensions(
            db, data=data, current_user=current_user
        )

        if wh.location_id is None:
            raise HTTPException(409, "Warehouse must be assigned to a Location before Stock Opname")
        if wh.location_id != loc:
            raise HTTPException(
                422,
                f"Warehouse {wh.code} belongs to Location {wh.location.name if wh.location else wh.location_id}, "
                "not the selected Stock Opname Location",
            )

        active_opname = (
            db.query(StockOpname)
            .filter(
                StockOpname.warehouse_id == wh.id,
                StockOpname.status.in_(["DRAFT", "PENDING_APPROVAL", "APPROVED"]),
            )
            .order_by(StockOpname.id.desc())
            .first()
        )
        if active_opname:
            raise HTTPException(
                409,
                detail={
                    "code": "ACTIVE_STOCK_OPNAME",
                    "message": (
                        f"Warehouse {wh.code} already has active Stock Opname "
                        f"{active_opname.opname_number} ({active_opname.status})."
                    ),
                    "opname_id": active_opname.id,
                    "opname_number": active_opname.opname_number,
                    "status": active_opname.status,
                },
            )
        op = StockOpname(
            opname_number=next_document_number(db, "SO"),
            status="DRAFT",
            count_date=data.count_date or date.today(),
            warehouse_id=wh.id,
            business_unit_id=bu,
            location_id=loc,
            department_id=dep,
            created_by_id=current_user.id,
            notes=data.notes,
        )
        for inv in (
            db.query(Inventory)
            .filter(Inventory.warehouse_id == wh.id)
            .order_by(Inventory.product_id)
            .all()
        ):
            product = db.get(Product, inv.product_id)
            if product and product.is_active:
                op.items.append(
                    StockOpnameItem(
                        product_id=product.id,
                        system_quantity=Decimal(inv.quantity or 0),
                        unit_cost=Decimal(inv.average_cost or 0),
                        uom=product.uom,
                    )
                )
        if not op.items:
            raise HTTPException(
                409,
                detail={
                    "code": "EMPTY_STOCK_SNAPSHOT",
                    "message": (
                        f"Warehouse {wh.code} has no active inventory lines. "
                        "Stock Opname cannot be created from an empty snapshot."
                    ),
                    "warehouse_id": wh.id,
                    "warehouse_code": wh.code,
                },
            )

        db.add(op)
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            conflict = (
                db.query(StockOpname)
                .filter(
                    StockOpname.warehouse_id == wh.id,
                    StockOpname.status.in_(["DRAFT", "PENDING_APPROVAL", "APPROVED"]),
                )
                .order_by(StockOpname.id.desc())
                .first()
            )
            if conflict:
                raise HTTPException(
                    409,
                    detail={
                        "code": "ACTIVE_STOCK_OPNAME",
                        "message": (
                            f"Warehouse {wh.code} already has active Stock Opname "
                            f"{conflict.opname_number} ({conflict.status})."
                        ),
                        "opname_id": conflict.id,
                        "opname_number": conflict.opname_number,
                        "status": conflict.status,
                    },
                ) from exc
            raise
        AuditService.log(
            db=db,
            user=current_user,
            action="CREATE",
            entity_type="STOCK_OPNAME",
            entity_id=op.id,
            summary=f"Created {op.opname_number}",
            document_type="SO",
            document_number=op.opname_number,
            document_status=op.status,
        )
        db.commit()
        db.refresh(op)
        return op

    @staticmethod
    def update_counts(
        db: Session, *, opname_id: int, data: StockOpnameCountUpdate, current_user: User
    ) -> StockOpname:
        op = StockOpnameService._get(db, opname_id, lock=True)
        if op.status == "POSTED":
            raise HTTPException(
                409, "Stock Opname counts cannot be edited once posted"
            )
        by_id = {i.id: i for i in op.items}
        seen = set()
        for incoming in data.items:
            if incoming.item_id in seen:
                raise HTTPException(
                    409, f"Duplicate Stock Opname item {incoming.item_id}"
                )
            seen.add(incoming.item_id)
            item = by_id.get(incoming.item_id)
            if not item:
                raise HTTPException(
                    404, f"Stock Opname item {incoming.item_id} not found"
                )
            physical = Decimal(incoming.physical_quantity)
            item.physical_quantity = physical
            item.variance_quantity = physical - Decimal(item.system_quantity)
        if data.notes is not None:
            op.notes = data.notes
        AuditService.log(
            db=db,
            user=current_user,
            action="COUNT",
            entity_type="STOCK_OPNAME",
            entity_id=op.id,
            summary=f"Updated physical count {op.opname_number}",
            document_type="SO",
            document_number=op.opname_number,
            document_status=op.status,
        )
        db.commit()
        db.refresh(op)
        return op

    @staticmethod
    def submit(db: Session, *, opname_id: int, current_user: User) -> StockOpname:
        op = StockOpnameService._get(db, opname_id, lock=True)
        if op.status not in ("DRAFT", "REJECTED"):
            raise HTTPException(409, "Only draft or rejected Stock Opname can be submitted")
        if not op.items:
            raise HTTPException(409, "Stock Opname has no inventory snapshot")
        missing = [i.product.code for i in op.items if i.physical_quantity is None]
        if missing:
            raise HTTPException(
                409, "Physical count is incomplete: " + ", ".join(missing[:10])
            )
        if op.status == "REJECTED":
            reset_approval(db, entity_type="STOCK_OPNAME", entity_id=op.id)
        start_approval(
            db,
            entity_type="STOCK_OPNAME",
            entity_id=op.id,
            workflow_code="SO_APPROVAL",
            user=current_user,
        )
        op.status = "PENDING_APPROVAL"
        op.submitted_at = datetime.now(timezone.utc)
        AuditService.log(
            db=db,
            user=current_user,
            action="SUBMIT",
            entity_type="STOCK_OPNAME",
            entity_id=op.id,
            summary=f"Submitted {op.opname_number}",
            document_type="SO",
            document_number=op.opname_number,
            document_status=op.status,
        )
        db.commit()
        db.refresh(op)
        return op

    @staticmethod
    def approve(
        db: Session,
        *,
        opname_id: int,
        data: ApprovalDecisionRequest | None,
        current_user: User,
    ) -> StockOpname:
        op = StockOpnameService._get(db, opname_id, lock=True)
        if op.status != "PENDING_APPROVAL":
            raise HTTPException(409, "Stock Opname does not have pending approval")
        if not op.items:
            raise HTTPException(409, "Stock Opname has no inventory snapshot and cannot be approved")
        req = get_request(db, "STOCK_OPNAME", op.id, for_update=True)
        if not req:
            raise HTTPException(500, "Approval workflow not found")
        approve_current_step(
            db, request=req, user=current_user, comment=data.comment if data else None
        )
        db.flush()
        db.refresh(req)
        if req.status == "APPROVED":
            op.status = "APPROVED"
        AuditService.log(
            db=db,
            user=current_user,
            action="APPROVE",
            entity_type="STOCK_OPNAME",
            entity_id=op.id,
            summary=f"Approved stage for {op.opname_number}",
            document_type="SO",
            document_number=op.opname_number,
            document_status=op.status,
        )
        db.commit()
        db.refresh(op)
        return op

    @staticmethod
    def reject(
        db: Session,
        *,
        opname_id: int,
        data: ApprovalDecisionRequest | None,
        current_user: User,
    ) -> StockOpname:
        op = StockOpnameService._get(db, opname_id, lock=True)
        if op.status != "PENDING_APPROVAL":
            raise HTTPException(409, "Stock Opname does not have pending approval")
        req = get_request(db, "STOCK_OPNAME", op.id, for_update=True)
        if not req:
            raise HTTPException(500, "Approval workflow not found")
        reject_current_step(
            db, request=req, user=current_user, comment=data.comment if data else None
        )
        op.status = "REJECTED"
        AuditService.log(
            db=db,
            user=current_user,
            action="REJECT",
            entity_type="STOCK_OPNAME",
            entity_id=op.id,
            summary=f"Rejected {op.opname_number}",
            document_type="SO",
            document_number=op.opname_number,
            document_status=op.status,
        )
        db.commit()
        db.refresh(op)
        return op

    @staticmethod
    def post(db: Session, *, opname_id: int, current_user: User) -> StockOpname:
        op = StockOpnameService._get(db, opname_id, lock=True)
        if op.status != "APPROVED":
            raise HTTPException(409, "Only approved Stock Opname can be posted")
        if not op.items:
            raise HTTPException(409, "Stock Opname has no inventory snapshot and cannot be posted")
        if op.posted_at is not None:
            raise HTTPException(409, "Stock Opname is already posted")
        prepared = []
        for item in sorted(op.items, key=lambda r: (r.product_id, r.id)):
            if item.physical_quantity is None:
                raise HTTPException(
                    409, "Stock Opname contains an incomplete physical count"
                )
            inv = (
                db.query(Inventory)
                .filter(
                    Inventory.warehouse_id == op.warehouse_id,
                    Inventory.product_id == item.product_id,
                )
                .with_for_update()
                .first()
            )
            if not inv:
                raise HTTPException(
                    409, f"Inventory row for {item.product.code} no longer exists"
                )
            if Decimal(inv.quantity or 0) != Decimal(item.system_quantity):
                raise HTTPException(
                    409,
                    f"Stock changed after snapshot for {item.product.code}; create a new Stock Opname",
                )
            prepared.append((item, inv))
        for item, inv in prepared:
            physical = Decimal(item.physical_quantity)
            variance = physical - Decimal(item.system_quantity)
            item.variance_quantity = variance
            inv.quantity = physical
            if variance != ZERO:
                db.add(
                    StockMovement(
                        product_id=item.product_id,
                        warehouse_id=op.warehouse_id,
                        business_unit_id=op.business_unit_id,
                        location_id=op.location_id,
                        department_id=op.department_id,
                        movement_type="IN" if variance > 0 else "OUT",
                        quantity=variance,
                        unit_cost=Decimal(item.unit_cost or 0),
                        reference_type="STOCK_OPNAME",
                        reference_id=op.id,
                        notes=f"Stock Opname adjustment {op.opname_number}",
                    )
                )
        op.status = "POSTED"
        op.posted_at = datetime.now(timezone.utc)
        op.posted_by_id = current_user.id
        AuditService.log(
            db=db,
            user=current_user,
            action="POST",
            entity_type="STOCK_OPNAME",
            entity_id=op.id,
            summary=f"Posted {op.opname_number}",
            document_type="SO",
            document_number=op.opname_number,
            document_status=op.status,
        )
        db.commit()
        db.refresh(op)
        return op

    @staticmethod
    def unpost(db: Session, *, opname_id: int, current_user: User) -> StockOpname:
        op = StockOpnameService._get(db, opname_id, lock=True)
        if op.status != "POSTED":
            raise HTTPException(409, "Only posted Stock Opname can be unposted")
        if op.posted_at is None:
            raise HTTPException(409, "Stock Opname is not posted")
        for item in op.items:
            inv = (
                db.query(Inventory)
                .filter(
                    Inventory.warehouse_id == op.warehouse_id,
                    Inventory.product_id == item.product_id,
                )
                .with_for_update()
                .first()
            )
            if not inv:
                raise HTTPException(
                    409, f"Inventory row for {item.product.code} no longer exists"
                )
            variance = Decimal(item.variance_quantity or 0)
            matched = (
                db.query(StockMovement)
                .filter(
                    StockMovement.reference_type == "STOCK_OPNAME",
                    StockMovement.reference_id == op.id,
                    StockMovement.product_id == item.product_id,
                )
                .order_by(StockMovement.id.desc())
                .first()
            )
            if matched:
                db.delete(matched)
            if variance != ZERO:
                inv.quantity = Decimal(inv.quantity or 0) - variance
            item.variance_quantity = None
        op.status = "APPROVED"
        op.posted_at = None
        op.posted_by_id = None
        AuditService.log(
            db=db,
            user=current_user,
            action="UNPOST",
            entity_type="STOCK_OPNAME",
            entity_id=op.id,
            summary=f"Unposted {op.opname_number}",
            document_type="SO",
            document_number=op.opname_number,
            document_status=op.status,
        )
        db.commit()
        db.refresh(op)
        return op
