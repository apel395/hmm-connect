from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class GoodsReceiptItemCreate(BaseModel):
    purchase_order_item_id: int | None = None
    product_id: int | None = None
    quantity: Decimal = Field(gt=0)
    unit_cost: Decimal | None = Field(default=None, gt=0)
    is_taxable: bool = False
    tax_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100)

    @model_validator(mode="after")
    def validate_tax(self):
        if not self.is_taxable:
            self.tax_rate = Decimal("0")
        return self


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
    cost_correction_reason: str | None = Field(default=None, max_length=500)
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


class GoodsReceiptCostCorrectionLine(BaseModel):
    item_id: int
    unit_cost: Decimal = Field(gt=0)


class GoodsReceiptCostCorrection(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
    items: list[GoodsReceiptCostCorrectionLine]

    @model_validator(mode="after")
    def validate_items(self):
        if not self.items:
            raise ValueError("At least one receipt item cost is required")
        if len({item.item_id for item in self.items}) != len(self.items):
            raise ValueError("A receipt item may appear only once")
        return self
