from datetime import date

from pydantic import BaseModel
from decimal import Decimal


class PaymentCreate(BaseModel):
    account_payable_id: int
    payment_date: date
    amount: Decimal
    payment_method: str
    reference_number: str | None = None


class PaymentResponse(BaseModel):
    id: int
    payment_number: str
    account_payable_id: int
    payment_date: date
    amount: Decimal
    payment_method: str
    status: str

    class Config:
        from_attributes = True