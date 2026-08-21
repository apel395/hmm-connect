from decimal import Decimal
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.stock_movement import StockMovement
from app.models.warehouse import Warehouse
from app.services.location_access import apply_warehouse_scope, resolve_location_id


router = APIRouter(prefix="/inventory", tags=["Inventory"])


def _paged(rows, *, page: int, page_size: int, total: int):
    total_pages = ceil(total / page_size) if total else 0
    return {
        "items": rows,
        "page": page,
        "page_size": page_size,
        "total_items": total,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_previous": page > 1,
    }


def inventory_row(inventory: Inventory, product: Product, warehouse: Warehouse):
    quantity = Decimal(inventory.quantity or 0)
    average_cost = Decimal(inventory.average_cost or 0)
    minimum_stock = Decimal(product.minimum_stock or 0)
    is_monitored = minimum_stock > 0
    is_low_stock = is_monitored and quantity <= minimum_stock
    shortage = max(minimum_stock - quantity, Decimal("0")) if is_low_stock else Decimal("0")
    return {
        "id": inventory.id,
        "product_id": product.id,
        "product_code": product.code,
        "product_name": product.name,
        "uom": product.uom,
        "warehouse_id": warehouse.id,
        "warehouse_code": warehouse.code,
        "warehouse_name": warehouse.name,
        "quantity": quantity,
        "average_cost": average_cost,
        "stock_value": quantity * average_cost,
        "minimum_stock": minimum_stock,
        "low_stock": is_low_stock,
        "shortage": shortage,
        # Compatibility fields for older UI clients. Both now follow the one
        # canonical business rule: current warehouse stock <= item minimum.
        "below_minimum": is_low_stock,
        "needs_reorder": is_low_stock,
    }


def _inventory_base(db: Session, user, warehouse_id: int | None = None):
    query = (
        db.query(Inventory, Product, Warehouse)
        .join(Product, Product.id == Inventory.product_id)
        .join(Warehouse, Warehouse.id == Inventory.warehouse_id)
        .filter(Product.is_active.is_(True), Warehouse.is_active.is_(True))
    )
    query = apply_warehouse_scope(query, user)
    if warehouse_id:
        query = query.filter(Inventory.warehouse_id == warehouse_id)
    return query


@router.get("")
def list_inventory(
    warehouse_id: int | None = None,
    health: str | None = Query(default=None, pattern="^(HEALTHY|LOW_STOCK|REORDER|BELOW_MINIMUM)$"),
    search: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    quantity = func.coalesce(Inventory.quantity, 0)
    minimum = func.coalesce(Product.minimum_stock, 0)
    monitored = minimum > 0
    low_stock = monitored & (quantity <= minimum)

    user = _
    summary_rows = _inventory_base(db, user, warehouse_id).with_entities(
        func.count(Inventory.id),
        func.coalesce(func.sum(quantity * func.coalesce(Inventory.average_cost, 0)), 0),
        func.coalesce(func.sum(case((monitored, 1), else_=0)), 0),
        func.coalesce(func.sum(case((low_stock, 1), else_=0)), 0),
    ).one()

    query = _inventory_base(db, user, warehouse_id)
    # REORDER and BELOW_MINIMUM remain accepted as compatibility aliases.
    if health in {"LOW_STOCK", "REORDER", "BELOW_MINIMUM"}:
        query = query.filter(minimum > 0, quantity <= minimum)
    elif health == "HEALTHY":
        query = query.filter(or_(minimum <= 0, quantity > minimum))
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(or_(Product.code.ilike(term), Product.name.ilike(term), Warehouse.name.ilike(term)))
    total = query.count()
    rows = query.order_by(Product.code, Warehouse.code).offset((page - 1) * page_size).limit(page_size).all()
    result = _paged([inventory_row(*row) for row in rows], page=page, page_size=page_size, total=total)
    result["summary"] = {
        "stock_lines": int(summary_rows[0] or 0),
        "stock_value": summary_rows[1] or 0,
        "monitored_lines": int(summary_rows[2] or 0),
        "low_stock": int(summary_rows[3] or 0),
        # Compatibility aliases for older clients.
        "needs_reorder": int(summary_rows[3] or 0),
        "below_minimum": int(summary_rows[3] or 0),
    }
    return result


@router.get("/movements")
def list_movements(
    product_id: int | None = None,
    warehouse_id: int | None = None,
    purchase_order_id: int | None = None,
    goods_receipt_id: int | None = None,
    location_id: int | None = None,
    department_id: int | None = None,
    search: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    user = _
    location_id = resolve_location_id(user, location_id)
    query = (
        db.query(StockMovement, Product, Warehouse)
        .join(Product, Product.id == StockMovement.product_id)
        .join(Warehouse, Warehouse.id == StockMovement.warehouse_id)
    )
    query = apply_warehouse_scope(query, user)
    if product_id:
        query = query.filter(StockMovement.product_id == product_id)
    if warehouse_id:
        query = query.filter(StockMovement.warehouse_id == warehouse_id)
    if purchase_order_id:
        query = query.filter(StockMovement.purchase_order_id == purchase_order_id)
    if goods_receipt_id:
        query = query.filter(StockMovement.goods_receipt_id == goods_receipt_id)
    if location_id:
        query = query.filter(StockMovement.location_id == location_id)
    if department_id:
        query = query.filter(StockMovement.department_id == department_id)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(or_(Product.code.ilike(term), Product.name.ilike(term), Warehouse.name.ilike(term)))

    total = query.count()
    rows = query.order_by(StockMovement.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    items = [
        {
            "id": movement.id,
            "movement_number": f"SM-{movement.id:08d}",
            "movement_date": movement.created_at,
            "movement_type": movement.movement_type,
            "product_id": product.id,
            "product_code": product.code,
            "product_name": product.name,
            "warehouse_id": warehouse.id,
            "warehouse_name": warehouse.name,
            "quantity": movement.quantity,
            "unit_cost": movement.unit_cost,
            "movement_value": Decimal(movement.quantity or 0) * Decimal(movement.unit_cost or 0),
            "reference_type": movement.reference_type,
            "reference_id": movement.reference_id,
            "goods_receipt_id": movement.goods_receipt_id,
            "goods_receipt_item_id": movement.goods_receipt_item_id,
            "receipt_number": movement.goods_receipt.receipt_number if movement.goods_receipt else None,
            "purchase_order_id": movement.purchase_order_id,
            "purchase_order_item_id": movement.purchase_order_item_id,
            "purchase_order_number": movement.purchase_order.po_number if movement.purchase_order else None,
            "business_unit_id": movement.business_unit_id,
            "location_id": movement.location_id,
            "department_id": movement.department_id,
            "reference_number": (
                movement.goods_receipt.receipt_number
                if movement.goods_receipt
                else movement.purchase_order.po_number
                if movement.purchase_order
                else f"{movement.reference_type}-{movement.reference_id}"
                if movement.reference_type and movement.reference_id
                else "-"
            ),
            "notes": movement.notes,
        }
        for movement, product, warehouse in rows
    ]
    return _paged(items, page=page, page_size=page_size, total=total)


@router.get("/{inventory_id}")
def get_inventory(
    inventory_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    user = _
    row = (
        apply_warehouse_scope(db.query(Inventory, Product, Warehouse), user)
        .join(Product, Product.id == Inventory.product_id)
        .join(Warehouse, Warehouse.id == Inventory.warehouse_id)
        .filter(Inventory.id == inventory_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Inventory record not found")
    return inventory_row(*row)
