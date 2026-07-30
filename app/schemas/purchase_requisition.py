from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class PurchaseRequisitionItemCreate(BaseModel):
    product_id: int
    quantity: Decimal = Field(gt=0)
    estimated_price: Decimal = Field(ge=0)


class PurchaseRequisitionCreate(BaseModel):
    request_date: date | None = None
    source_type: Literal["LIVE", "HISTORICAL_IMPORT"] = "LIVE"
    external_reference: str | None = Field(default=None, max_length=100)
    notes: str | None = None
    expiry_date: date | None = None
    items: list[PurchaseRequisitionItemCreate]


class PurchaseRequisitionConvertCreate(BaseModel):
    supplier_id: int
