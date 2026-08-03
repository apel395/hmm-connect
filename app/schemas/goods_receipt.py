from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class GoodsReceiptItemCreate(BaseModel):
    purchase_order_item_id: int
    quantity: Decimal = Field(gt=0)


class GoodsReceiptCreate(BaseModel):
    purchase_order_id: int
    received_at: datetime | None = None
    source_type: Literal["LIVE", "HISTORICAL_IMPORT"] = "LIVE"
    external_reference: str | None = Field(default=None, max_length=100)
    receipt_type: Literal["GOODS", "SERVICE"] = "GOODS"
    warehouse_id: int | None = None
    destination_type: Literal["WAREHOUSE", "DIRECT_USE"] = "WAREHOUSE"
    notes: str | None = None
    items: list[GoodsReceiptItemCreate]
