from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class GoodsReceiptItemCreate(BaseModel):
    purchase_order_item_id: int
    quantity: Decimal = Field(gt=0)


class GoodsReceiptCreate(BaseModel):
    purchase_order_id: int
    warehouse_id: int
    destination_type: Literal["INVENTORY", "DIRECT_CONSUMPTION"] = "INVENTORY"
    notes: str | None = None
    items: list[GoodsReceiptItemCreate]