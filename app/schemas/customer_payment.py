from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class CustomerPaymentCreate(BaseModel):

    cash_account_id: int | None = Field(default=None, gt=0)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=64)
    account_receivable_id: int
    payment_date: date
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    payment_method: str
    reference_number: str | None = None


class CustomerPaymentResponse(BaseModel):

    id: int
    payment_number: str
    account_receivable_id: int
    payment_date: date
    amount: Decimal
    payment_method: str
    reference_number: str | None
    status: str

    class Config:
        from_attributes = True
