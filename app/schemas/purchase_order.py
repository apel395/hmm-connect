from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


class PurchaseOrderItemCreate(BaseModel):
    product_id: int
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    purchase_requisition_item_id: int


class PurchaseOrderCreate(BaseModel):
    supplier_id: int
    expected_date: date
    expiry_date: date | None = None
    receipt_tolerance_percent: Decimal = Field(default=Decimal("0"), ge=0)
    notes: str | None = None
    purchase_requisition_ids: list[int]
    items: list[PurchaseOrderItemCreate]

    @model_validator(mode="after")
    def validate_dates_and_items(self):
        if not self.purchase_requisition_ids:
            raise ValueError("At least one approved purchase requisition is required")
        if not self.items:
            raise ValueError("Purchase order must have items")
        if self.expiry_date and self.expiry_date < self.expected_date:
            raise ValueError("Expiry date cannot be before expected date")
        return self