from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class StoreRequestItemCreate(BaseModel):
    product_id: int
    quantity: Decimal = Field(gt=0)


class StoreRequestCreate(BaseModel):
    request_date: date | None = None
    business_unit_id: int | None = None
    department_id: int | None = None
    location_id: int | None = None
    warehouse_id: int
    notes: str | None = None
    items: list[StoreRequestItemCreate] = Field(min_length=1)


class StoreRequestIssueItem(BaseModel):
    item_id: int
    quantity: Decimal = Field(gt=0)


class StoreRequestIssueCreate(BaseModel):
    issue_date: date | None = None
    items: list[StoreRequestIssueItem] = Field(min_length=1)
    notes: str | None = None
