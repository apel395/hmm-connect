from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class GoodsReceiptItemCreate(BaseModel):
    purchase_order_item_id: int | None = None
    product_id: int | None = None
    quantity: Decimal = Field(gt=0)
    unit_cost: Decimal | None = Field(default=None, ge=0)


class GoodsReceiptCreate(BaseModel):
    business_unit_id: int | None = None
    location_id: int | None = None
    department_id: int | None = None
    purchase_order_id: int | None = None
    supplier_id: int | None = None
    received_at: datetime | None = None
    source_type: Literal["LIVE", "HISTORICAL_IMPORT"] = "LIVE"
    external_reference: str | None = Field(default=None, max_length=100)
    receipt_type: Literal["GOODS", "SERVICE"] = "GOODS"
    warehouse_id: int | None = None
    destination_type: Literal["WAREHOUSE", "DIRECT_USE"] = "WAREHOUSE"
    notes: str | None = None
    items: list[GoodsReceiptItemCreate]

    @model_validator(mode="after")
    def validate_source(self):
        if not self.items:
            raise ValueError("Receipt must contain items")
        if self.purchase_order_id:
            if any(item.purchase_order_item_id is None for item in self.items):
                raise ValueError("PO receipts require purchase_order_item_id for every line")
        else:
            if self.supplier_id is None:
                raise ValueError("Direct receipts require supplier_id")
            if self.business_unit_id is None or self.department_id is None or self.location_id is None:
                raise ValueError("Direct receipts require business unit, department and location")
            if any(item.product_id is None or item.unit_cost is None for item in self.items):
                raise ValueError("Direct receipt lines require product_id and unit_cost")
        return self
