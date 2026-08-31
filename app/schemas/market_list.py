from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class MarketListItemCreate(BaseModel):
    product_id: int
    quantity: Decimal = Field(gt=0)
    estimated_price: Decimal = Field(ge=0)


class MarketListCreate(BaseModel):
    business_unit_id: int | None = None
    location_id: int | None = None
    department_id: int | None = None
    request_date: date | None = None
    source_type: Literal["LIVE", "HISTORICAL_IMPORT"] = "LIVE"
    external_reference: str | None = Field(default=None, max_length=100)
    notes: str | None = None
    expiry_date: date | None = None
    items: list[MarketListItemCreate]


class MarketListConvertItem(BaseModel):
    market_list_item_id: int
    quantity: Decimal = Field(gt=0)


class MarketListConvertCreate(BaseModel):
    supplier_id: int
    items: list[MarketListConvertItem] | None = None
