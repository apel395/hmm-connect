from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.warehouse import Warehouse

router = APIRouter(prefix="/inventory", tags=["Inventory"])


class InventoryResponse(BaseModel):
    product_id: int
    code: str
    name: str
    uom: str
    warehouse_id: int
    warehouse_code: str
    warehouse_name: str
    quantity: Decimal
    average_cost: Decimal


@router.get("", response_model=list[InventoryResponse])
def get_inventory(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    rows = (
        db.query(
            Inventory.product_id,
            Inventory.warehouse_id,
            Inventory.quantity,
            Inventory.average_cost,
            Product.code,
            Product.name,
            Product.uom,
            Warehouse.code.label("warehouse_code"),
            Warehouse.name.label("warehouse_name"),
        )
        .join(Product, Product.id == Inventory.product_id)
        .join(Warehouse, Warehouse.id == Inventory.warehouse_id)
        .order_by(Warehouse.code, Product.code)
        .all()
    )

    return [
        InventoryResponse(
            product_id=row.product_id,
            code=row.code,
            name=row.name,
            uom=row.uom,
            warehouse_id=row.warehouse_id,
            warehouse_code=row.warehouse_code,
            warehouse_name=row.warehouse_name,
            quantity=row.quantity,
            average_cost=row.average_cost,
        )
        for row in rows
    ]
