from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.stock_movement import StockMovement
from app.models.warehouse import Warehouse


router = APIRouter(prefix="/inventory", tags=["Inventory"])


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
    return [
        {
            "id": inventory.id,
            "product_id": product.id,
            "product_code": product.code,
            "product_name": product.name,
            "uom": product.uom,
            "warehouse_id": warehouse.id,
            "warehouse_code": warehouse.code,
            "warehouse_name": warehouse.name,
            "quantity": inventory.quantity,
            "average_cost": inventory.average_cost,
        }
        for inventory, product, warehouse in query.order_by(Product.code).all()
    ]


@router.get("/movements")
def list_movements(
    product_id: int | None = None,
    warehouse_id: int | None = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    query = db.query(StockMovement)
    if product_id:
        query = query.filter(StockMovement.product_id == product_id)
    if warehouse_id:
        query = query.filter(StockMovement.warehouse_id == warehouse_id)
    return query.order_by(StockMovement.id.desc()).limit(500).all()
