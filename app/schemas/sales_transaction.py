from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SalesTransactionItemIn(BaseModel):
    product_id: int
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal | None = Field(default=None, ge=0)


class SalesTransactionCreate(BaseModel):
    revenue_account_id: int | None = Field(default=None, gt=0)
    warehouse_id: int | None = None
    transaction_type: Literal["POS", "INVOICE"] = "POS"
    table_number: str | None = Field(default=None, max_length=30)
    queue_number: str | None = Field(default=None, max_length=50)
    sale_date: date | None = None
    customer_id: int | None = None
    business_unit_id: int | None = None
    location_id: int | None = None
    department_id: int | None = None
    notes: str | None = None
    items: list[SalesTransactionItemIn] = Field(default_factory=list)


class SalesTransactionUpdate(BaseModel):
    revenue_account_id: int | None = Field(default=None, gt=0)
    transaction_type: Literal["POS", "INVOICE"] | None = None
    table_number: str | None = Field(default=None, max_length=30)
    queue_number: str | None = Field(default=None, max_length=50)
    sale_date: date | None = None
    customer_id: int | None = None
    notes: str | None = None
    items: list[SalesTransactionItemIn] = Field(default_factory=list)


class SalesTransactionPost(BaseModel):
    revenue_account_id: int | None = Field(default=None, gt=0)
    payment_method: Literal["CASH", "CARD", "BANK_TRANSFER"] = "CASH"
    payment_received: Decimal | None = Field(default=None, ge=0)
    discount_amount: Decimal | None = Field(default=None, ge=0)


class SalesTransactionVoid(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class SalesTransactionItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    line_number: int | None
    quantity: Decimal
    unit_price: Decimal
    tax_rate: Decimal
    tax_amount: Decimal
    line_amount: Decimal
    unit_cost: Decimal
    uom: str
