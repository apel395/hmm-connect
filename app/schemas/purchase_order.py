from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class PurchaseOrderItemCreate(BaseModel):
    product_id: int | None = None
    description: str | None = None
    uom: str | None = Field(default=None, max_length=20)
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    purchase_requisition_item_id: int | None = None


class PurchaseOrderCreate(BaseModel):
    supplier_id: int
    department_id: int | None = None
    location_id: int | None = None
    order_date: date | None = None
    source_type: Literal["LIVE", "HISTORICAL_IMPORT"] = "LIVE"
    external_reference: str | None = Field(default=None, max_length=100)
    expected_date: date | None = None
    expiry_date: date | None = None
    notes: str | None = None
    purchase_requisition_ids: list[int] = Field(default_factory=list)
    items: list[PurchaseOrderItemCreate]

    @model_validator(mode="after")
    def validate_dates_and_items(self):
        if not self.items:
            raise ValueError("Purchase order must have items")
        if self.purchase_requisition_ids and any(item.purchase_requisition_item_id is None for item in self.items):
            raise ValueError("Items created from a requisition require a source requisition item")
        if not self.purchase_requisition_ids and any(item.purchase_requisition_item_id is not None for item in self.items):
            raise ValueError("Direct order items cannot reference a requisition item")
        if len(self.purchase_requisition_ids) > 1:
            raise ValueError("A purchase order can reference only one purchase requisition")
        if not self.purchase_requisition_ids and any(item.product_id is None for item in self.items):
            raise ValueError("Direct order items require a product")
        if not self.purchase_requisition_ids and self.expected_date is None:
            raise ValueError("Direct purchase orders require an estimated delivery date")
        if self.expiry_date and self.expected_date and self.expiry_date < self.expected_date:
            raise ValueError("Expiry date cannot be before expected date")
        return self
