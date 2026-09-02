from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.dependencies.authorization import has_permission
from app.models.inventory import Inventory
from app.models.location import Location
from app.models.product import Product
from app.models.stock_adjustment import StockAdjustment, StockAdjustmentItem
from app.models.stock_movement import StockMovement
from app.models.user import User
from app.models.warehouse import Warehouse
from app.schemas.stock_adjustment import (
    StockAdjustmentCreate,
    StockAdjustmentItemIn,
    StockAdjustmentUpdate,
)
from app.services.activity_service import ActivityService
from app.services.document_number import next_document_number
from app.services.location_access import apply_warehouse_scope
from app.services.organization_dimensions import validate_dimensions

ZERO = Decimal("0")
MONEY = Decimal("0.01")


class StockAdjustmentService:
    @staticmethod
    def _require(user: User, permission_code: str) -> None:
        if not has_permission(user, permission_code):
            raise HTTPException(403, f"{permission_code} permission required")

    @staticmethod
    def _get(db: Session, adjustment_id: int, *, lock: bool = False) -> StockAdjustment:
        query = db.query(StockAdjustment).filter(StockAdjustment.id == adjustment_id)
        query = query.with_for_update() if lock else query
        row = query.first()
        if not row:
            raise HTTPException(404, "Stock Adjustment not found")
        return row

    @staticmethod
    def _scoped_warehouse(db: Session, warehouse_id: int, user: User) -> Warehouse:
        warehouse = (
            apply_warehouse_scope(db.query(Warehouse), user)
            .filter(Warehouse.id == warehouse_id, Warehouse.is_active.is_(True))
            .first()
        )
        if not warehouse:
            raise HTTPException(404, "Active warehouse not found or outside your scope")
        if warehouse.location_id is None:
            raise HTTPException(409, "Warehouse must be assigned to a work location")
        return warehouse

    @staticmethod
    def _dimensions(db: Session, warehouse: Warehouse, data) -> tuple[int, int, int | None]:
        location: Location | None = db.get(Location, data.location_id or warehouse.location_id)
        if not location or not location.is_active:
            raise HTTPException(422, "Active Location is required for Stock Adjustment")
        if warehouse.location_id != location.id:
            raise HTTPException(
                422,
                f"Warehouse {warehouse.code} belongs to Location {warehouse.location_id}, "
                "not the selected adjustment Location",
            )
        business_unit_id = data.business_unit_id or location.business_unit_id
        if not business_unit_id:
            raise HTTPException(422, "Selected Location is not assigned to a Business Unit")
        department_id = data.department_id
        validate_dimensions(db, business_unit_id, location.id, department_id, True)
        return business_unit_id, location.id, department_id

    @staticmethod
    def _materialize_items(
        db: Session,
        adjustment: StockAdjustment,
        *,
        incoming: list[StockAdjustmentItemIn],
    ) -> list[StockAdjustmentItem]:
        seen: set[int] = set()
        materialized: list[StockAdjustmentItem] = []
        for line in incoming:
            if line.product_id in seen:
                raise HTTPException(400, f"Duplicate product {line.product_id} in adjustment items")
            seen.add(line.product_id)
            product = db.get(Product, line.product_id)
            if not product or not product.is_active:
                raise HTTPException(404, f"Active product {line.product_id} not found")
            inventory = (
                db.query(Inventory)
                .filter(
                    Inventory.warehouse_id == adjustment.warehouse_id,
                    Inventory.product_id == line.product_id,
                )
                .first()
            )
            if not inventory:
                raise HTTPException(
                    409,
                    f"Product {product.code} has no current stock in warehouse {adjustment.warehouse.code}",
                )
            adjusted = Decimal(line.adjusted_quantity)
            system = Decimal(inventory.quantity or 0)
            delta = adjusted - system
            unit_cost = Decimal(inventory.average_cost or 0)
            materialized.append(
                StockAdjustmentItem(
                    product_id=product.id,
                    system_quantity=system,
                    adjusted_quantity=adjusted,
                    delta_quantity=delta,
                    unit_cost=unit_cost,
                    uom=product.uom,
                    reason=line.reason or adjustment.reason,
                    line_value=(abs(delta) * unit_cost).quantize(MONEY),
                )
            )
        return materialized

    @staticmethod
    def _total(items: list[StockAdjustmentItem]) -> Decimal:
        return sum((Decimal(line.line_value or 0) for line in items), ZERO).quantize(MONEY)

    @classmethod
    def create(cls, db: Session, *, data: StockAdjustmentCreate, user: User) -> StockAdjustment:
        cls._require(user, "inventory.adjust")
        warehouse = cls._scoped_warehouse(db, data.warehouse_id, user)
        business_unit_id, location_id, department_id = cls._dimensions(db, warehouse, data)
        adjustment = StockAdjustment(
            adjustment_number=next_document_number(db, "ADJ", digits=5, day=True),
            status="DRAFT",
            adjustment_date=data.adjustment_date or date.today(),
            warehouse_id=warehouse.id,
            business_unit_id=business_unit_id,
            location_id=location_id,
            department_id=department_id,
            reason=data.reason,
            notes=data.notes,
            created_by_id=user.id,
        )
        if data.items:
            adjustment.items = cls._materialize_items(db, adjustment, incoming=data.items)
            adjustment.total_adjustment_value = cls._total(adjustment.items)
        db.add(adjustment)
        db.flush()
        ActivityService.log(
            db=db,
            user=user,
            action="CREATE",
            entity_type="STOCK_ADJUSTMENT",
            entity_id=adjustment.id,
            summary=f"Created {adjustment.adjustment_number}",
            document_type="ADJ",
            document_number=adjustment.adjustment_number,
            document_status=adjustment.status,
            reference_document=warehouse.code,
            details={"warehouse_id": warehouse.id, "reason": data.reason, "item_count": len(adjustment.items)},
        )
        db.commit()
        db.refresh(adjustment)
        return adjustment

    @classmethod
    def update(
        cls,
        db: Session,
        *,
        adjustment: StockAdjustment,
        data: StockAdjustmentUpdate,
        user: User,
    ) -> StockAdjustment:
        cls._require(user, "inventory.adjust")
        if adjustment.status != "DRAFT":
            raise HTTPException(409, "Only draft Stock Adjustments can be edited")
        if data.reason is not None:
            adjustment.reason = data.reason
        if data.notes is not None:
            adjustment.notes = data.notes
        if data.adjustment_date is not None:
            adjustment.adjustment_date = data.adjustment_date
        adjustment.items = cls._materialize_items(db, adjustment, incoming=data.items)
        adjustment.total_adjustment_value = cls._total(adjustment.items)
        ActivityService.log(
            db=db,
            user=user,
            action="UPDATE",
            entity_type="STOCK_ADJUSTMENT",
            entity_id=adjustment.id,
            summary=f"Updated {adjustment.adjustment_number}",
            document_type="ADJ",
            document_number=adjustment.adjustment_number,
            document_status=adjustment.status,
            details={"item_count": len(adjustment.items), "reason": adjustment.reason},
        )
        db.commit()
        db.refresh(adjustment)
        return adjustment

    @classmethod
    def post(cls, db: Session, *, adjustment_id: int, user: User) -> StockAdjustment:
        cls._require(user, "inventory.adjust")
        adjustment = cls._get(db, adjustment_id, lock=True)
        if adjustment.status != "DRAFT":
            raise HTTPException(409, "Only draft Stock Adjustments can be posted")
        if not adjustment.items:
            raise HTTPException(409, "Stock Adjustment has no items to post")
        if not any(Decimal(item.delta_quantity or 0) != ZERO for item in adjustment.items):
            raise HTTPException(409, "Stock Adjustment must change at least one item quantity")

        prepared = []
        for item in sorted(adjustment.items, key=lambda row: (row.product_id, row.id)):
            inventory = (
                db.query(Inventory)
                .filter(
                    Inventory.warehouse_id == adjustment.warehouse_id,
                    Inventory.product_id == item.product_id,
                )
                .with_for_update()
                .first()
            )
            if not inventory:
                raise HTTPException(409, f"Inventory row for product {item.product_id} no longer exists")
            if Decimal(inventory.quantity or 0) != Decimal(item.system_quantity):
                raise HTTPException(
                    409,
                    f"Stock changed after adjustment for product {item.product_id}; "
                    "edit the adjustment and re-snapshot the quantities",
                )
            prepared.append((item, inventory))

        for item, inventory in prepared:
            delta = Decimal(item.delta_quantity)
            inventory.quantity = Decimal(item.adjusted_quantity)
            if Decimal(inventory.quantity) == ZERO:
                inventory.average_cost = ZERO
            db.add(
                StockMovement(
                    product_id=item.product_id,
                    warehouse_id=adjustment.warehouse_id,
                    business_unit_id=adjustment.business_unit_id,
                    location_id=adjustment.location_id,
                    department_id=adjustment.department_id,
                    movement_type="IN" if delta > ZERO else "OUT",
                    quantity=abs(delta),
                    unit_cost=Decimal(item.unit_cost or 0),
                    reference_type="STOCK_ADJUSTMENT",
                    reference_id=adjustment.id,
                    notes=f"Stock adjustment {adjustment.adjustment_number}: {item.reason or adjustment.reason}",
                )
            )

        adjustment.status = "POSTED"
        adjustment.posted_at = datetime.now(timezone.utc)
        adjustment.posted_by_id = user.id
        ActivityService.log(
            db=db,
            user=user,
            action="POST",
            entity_type="STOCK_ADJUSTMENT",
            entity_id=adjustment.id,
            summary=f"Posted {adjustment.adjustment_number}",
            document_type="ADJ",
            document_number=adjustment.adjustment_number,
            document_status=adjustment.status,
            details={"value": str(adjustment.total_adjustment_value)},
        )
        db.commit()
        db.refresh(adjustment)
        return adjustment

    @classmethod
    def void(cls, db: Session, *, adjustment_id: int, user: User) -> StockAdjustment:
        cls._require(user, "inventory.adjust")
        adjustment = cls._get(db, adjustment_id, lock=True)
        if adjustment.status == "POSTED":
            raise HTTPException(409, "Posted Stock Adjustments cannot be voided; create a reversing adjustment")
        if adjustment.status == "VOID":
            raise HTTPException(409, "Stock Adjustment is already voided")
        adjustment.status = "VOID"
        ActivityService.log(
            db=db,
            user=user,
            action="VOID",
            entity_type="STOCK_ADJUSTMENT",
            entity_id=adjustment.id,
            summary=f"Voided {adjustment.adjustment_number}",
            document_type="ADJ",
            document_number=adjustment.adjustment_number,
            document_status=adjustment.status,
        )
        db.commit()
        db.refresh(adjustment)
        return adjustment