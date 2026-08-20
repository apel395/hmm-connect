from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class StockOpnameCreate(BaseModel):
    warehouse_id: int
    count_date: date | None = None
    notes: str | None = None


class StockOpnameCountItem(BaseModel):
    item_id: int
    physical_quantity: Decimal = Field(ge=0)


class StockOpnameCountUpdate(BaseModel):
    items: list[StockOpnameCountItem]
    notes: str | None = None
