from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class ReceiveItem(BaseModel):
    purchase_order_item_id: int
    quantity: Decimal


class GoodsReceiptCreate(BaseModel):
    destination_type: str = "INVENTORY"
    warehouse_id: int | None = None
    items: list[ReceiveItem]
    notes: str | None = None


class GoodsReceiptItemResponse(BaseModel):
    id: int
    purchase_order_item_id: int
    product_id: int
    quantity: Decimal
    unit_cost: Decimal

    class Config:
        from_attributes = True


class GoodsReceiptResponse(BaseModel):
    id: int
    receipt_number: str
    purchase_order_id: int
    received_by_id: int | None
    received_at: datetime
    destination_type: str
    warehouse_id: int | None
    notes: str | None
    items: list[GoodsReceiptItemResponse]

    class Config:
        from_attributes = True
