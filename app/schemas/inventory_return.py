from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class ReturnItemInput(BaseModel):
    goods_receipt_item_id: int
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=2)


class ReturnInput(BaseModel):
    request_key: UUID = Field(default_factory=uuid4)
    goods_receipt_id: int
    purpose: Literal['REPLACEMENT', 'AP_CREDIT']
    return_date: date
    reason: str = Field(min_length=1, max_length=1000)
    clearing_account_id: int
    items: list[ReturnItemInput] = Field(min_length=1)


class ReplacementItemInput(BaseModel):
    return_item_id: int
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=2)


class ReplacementInput(BaseModel):
    received_date: date
    delivery_note: str = Field(min_length=1, max_length=100)
    items: list[ReplacementItemInput] = Field(min_length=1)


class ReturnCreditInput(BaseModel):
    supplier_invoice_id: int
    credit_date: date
    credit_reference: str = Field(min_length=1, max_length=150)
    net_amount: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    tax_amount: Decimal = Field(default=0, ge=0, max_digits=18, decimal_places=2)
    supplier_credit_account_id: int | None = None
    variance_account_id: int | None = None
