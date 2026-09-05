from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class PurchaseRequisitionItemCreate(BaseModel):
    product_id: int
    quantity: Decimal = Field(gt=0)
    estimated_price: Decimal = Field(gt=0)
    is_taxable: bool = False
    tax_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100)

    @model_validator(mode="after")
    def validate_tax(self):
        if not self.is_taxable:
            self.tax_rate = Decimal("0")
        return self


class PurchaseRequisitionCreate(BaseModel):
    business_unit_id: int | None = None
    location_id: int | None = None
    department_id: int | None = None
    request_date: date | None = None
    source_type: Literal["LIVE", "HISTORICAL_IMPORT"] = "LIVE"
    external_reference: str | None = Field(default=None, max_length=100)
    notes: str | None = None
    expiry_date: date | None = None
    items: list[PurchaseRequisitionItemCreate]


class PurchaseRequisitionConvertCreate(BaseModel):
    supplier_id: int
