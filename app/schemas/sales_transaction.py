from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.schemas.catering_billing import CateringBilling


class SalesTransactionItemIn(BaseModel):
    description: str | None = Field(default=None, max_length=1000)
    registration_number: str | None = Field(default=None, max_length=150)
    service_period_from: date | None = None
    service_period_to: date | None = None
    uom: str | None = Field(default=None, min_length=1, max_length=30)
    product_id: int
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal | None = Field(default=None, ge=0)


    @model_validator(mode="after")
    def valid_period(self):
        if self.service_period_from and self.service_period_to and self.service_period_to < self.service_period_from:
            raise ValueError("Service period end cannot precede its start")
        return self


class SalesTransactionCreate(BaseModel):
    guest_count: int | None = Field(default=None, ge=1, le=2147483647, strict=True)
    discount_preset_id: str | None = Field(default=None, max_length=64)
    checkout_version: str | None = Field(default=None, max_length=64)
    billing_details: CateringBilling | None = None
    pos_table_id: int | None = Field(default=None, gt=0)
    cashier_session_id: int | None = Field(default=None, gt=0)
    event_name: str | None = Field(default=None, max_length=200)
    order_request_key: str | None = Field(default=None, min_length=8, max_length=64)
    invoice_due_date: date | None = None
    receivable_account_id: int | None = Field(default=None, gt=0)
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
    guest_count: int | None = Field(default=None, ge=1, le=2147483647, strict=True)
    discount_preset_id: str | None = Field(default=None, max_length=64)
    checkout_version: str | None = Field(default=None, max_length=64)
    billing_details: CateringBilling | None = None
    location_id: int | None = Field(default=None, gt=0)
    department_id: int | None = Field(default=None, gt=0)
    invoice_due_date: date | None = None
    receivable_account_id: int | None = Field(default=None, gt=0)
    revenue_account_id: int | None = Field(default=None, gt=0)
    transaction_type: Literal["POS", "INVOICE"] | None = None
    table_number: str | None = Field(default=None, max_length=30)
    queue_number: str | None = Field(default=None, max_length=50)
    sale_date: date | None = None
    customer_id: int | None = None
    notes: str | None = None
    items: list[SalesTransactionItemIn] = Field(default_factory=list)


class SalesTransactionPost(BaseModel):
    discount_preset_id: str | None = Field(default=None, max_length=64)
    checkout_version: str | None = Field(default=None, max_length=64)
    invoice_due_date: date | None = None
    receivable_account_id: int | None = Field(default=None, gt=0)
    customer_id: int | None = Field(default=None, gt=0)
    revenue_account_id: int | None = Field(default=None, gt=0)
    payment_method: Literal["CASH", "CARD", "BANK_TRANSFER"] = "CASH"
    payment_received: Decimal | None = Field(default=None, ge=0)
    discount_amount: Decimal | None = Field(default=None, ge=0)


class SalesTransactionVoid(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class SalesTransactionItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    description: str | None = Field(default=None, max_length=1000)
    registration_number: str | None = Field(default=None, max_length=150)
    service_period_from: date | None = None
    service_period_to: date | None = None
    uom: str | None = Field(default=None, min_length=1, max_length=30)
    product_id: int
    line_number: int | None
    quantity: Decimal
    unit_price: Decimal
    tax_rate: Decimal
    tax_amount: Decimal
    line_amount: Decimal
    unit_cost: Decimal
    uom: str


class InvoiceARCorrection(BaseModel):
    customer_id: int = Field(gt=0)
    invoice_due_date: date
    receivable_account_id: int | None = Field(default=None, gt=0)
    correction_date: date
    confirm_unpaid: Literal[True]
