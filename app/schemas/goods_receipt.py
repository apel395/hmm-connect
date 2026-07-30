from decimal import Decimal

from pydantic import BaseModel, Field


class GoodsReceiptItemCreate(BaseModel):
    purchase_order_item_id: int
    quantity: Decimal = Field(gt=0)
    unit_cost: Decimal = Field(ge=0)


class GoodsReceiptCreate(BaseModel):
    purchase_order_id: int
    warehouse_id: int
    destination_type: str = "INVENTORY"
    notes: str | None = None
    items: list[GoodsReceiptItemCreate]
