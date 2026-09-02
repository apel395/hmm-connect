from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class StockAdjustmentItemIn(BaseModel):
    product_id: int
    adjusted_quantity: Decimal = Field(ge=0)
    reason: str | None = Field(default=None, max_length=1000)


class StockAdjustmentCreate(BaseModel):
    warehouse_id: int
    adjustment_date: date | None = None
    business_unit_id: int | None = None
    location_id: int | None = None
    department_id: int | None = None
    reason: str = Field(min_length=1, max_length=1000)
    notes: str | None = None
    items: list[StockAdjustmentItemIn] = Field(default_factory=list)


class StockAdjustmentUpdate(BaseModel):
    adjustment_date: date | None = None
    reason: str | None = Field(default=None, min_length=1, max_length=1000)
    notes: str | None = None
    items: list[StockAdjustmentItemIn] = Field(min_length=1)


class StockAdjustmentItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    system_quantity: Decimal
    adjusted_quantity: Decimal
    delta_quantity: Decimal
    unit_cost: Decimal
    uom: str
    reason: str | None
    line_value: Decimal


class StockAdjustmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    adjustment_number: str
    status: str
    adjustment_date: date
    warehouse_id: int
    business_unit_id: int | None
    location_id: int | None
    department_id: int | None
    reason: str
    notes: str | None
    created_by_id: int
    posted_at: datetime | None = None
    posted_by_id: int | None = None
    total_adjustment_value: Decimal