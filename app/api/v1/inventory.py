from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.stock_movement import StockMovement
from app.models.warehouse import Warehouse


router = APIRouter(prefix="/inventory", tags=["Inventory"])


def inventory_row(inventory: Inventory, product: Product, warehouse: Warehouse):
    quantity = Decimal(inventory.quantity or 0)
    average_cost = Decimal(inventory.average_cost or 0)
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
        "minimum_stock": product.minimum_stock,
        "reorder_level": product.reorder_level,
        "maximum_stock": product.maximum_stock,
        "below_minimum": quantity < Decimal(product.minimum_stock or 0),
        "needs_reorder": quantity <= Decimal(product.reorder_level or 0),
    }


@router.get("")
def list_inventory(
    warehouse_id: int | None = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    query = (
        db.query(Inventory, Product, Warehouse)
        .join(Product, Product.id == Inventory.product_id)
        .join(Warehouse, Warehouse.id == Inventory.warehouse_id)
    )
    if warehouse_id:
        query = query.filter(Inventory.warehouse_id == warehouse_id)
    return [inventory_row(inventory, product, warehouse) for inventory, product, warehouse in query.order_by(Product.code).all()]


@router.get("/movements")
def list_movements(
    product_id: int | None = None,
    warehouse_id: int | None = None,
    purchase_order_id: int | None = None,
    goods_receipt_id: int | None = None,
    location_id: int | None = None,
    department_id: int | None = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    query = (
        db.query(StockMovement, Product, Warehouse)
        .join(Product, Product.id == StockMovement.product_id)
        .join(Warehouse, Warehouse.id == StockMovement.warehouse_id)
    )
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

    rows = query.order_by(StockMovement.id.desc()).limit(500).all()
    return [
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


@router.get("/{inventory_id}")
def get_inventory(
    inventory_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    row = (
        db.query(Inventory, Product, Warehouse)
        .join(Product, Product.id == Inventory.product_id)
        .join(Warehouse, Warehouse.id == Inventory.warehouse_id)
        .filter(Inventory.id == inventory_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Inventory record not found")
    return inventory_row(*row)
