from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class CustomerPaymentCreate(BaseModel):

    account_receivable_id: int
    payment_date: date
    amount: Decimal = Field(gt=0)
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
