from typing import Literal
from pydantic import BaseModel, Field

EventType = Literal[
    "SUPPLIER_INVOICE_INVENTORY",
    "SUPPLIER_INVOICE_DIRECT_USE",
    "SUPPLIER_PAYMENT",
    "CUSTOMER_PAYMENT",
]


class PostingRuleCreate(BaseModel):
    event_type: EventType
    business_unit_id: int | None = None
    location_id: int | None = None
    debit_account_id: int
    credit_account_id: int
    input_vat_account_id: int | None = None
    description: str | None = Field(default=None, max_length=500)
    is_active: bool = True


class PostingRuleUpdate(BaseModel):
    event_type: EventType | None = None
    business_unit_id: int | None = None
    location_id: int | None = None
    debit_account_id: int | None = None
    credit_account_id: int | None = None
    input_vat_account_id: int | None = None
    description: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None
