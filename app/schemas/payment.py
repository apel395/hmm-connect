from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class PaymentAllocationInput(BaseModel):
    supplier_invoice_id: int
    allocated_amount: Decimal = Field(gt=0)


class PaymentFundingInput(BaseModel):
    bank_account_id: int
    amount: Decimal = Field(gt=0)


class PaymentCreate(BaseModel):
    business_unit_id: int | None = None
    location_id: int | None = None
    department_id: int | None = None
    supplier_id: int
    payment_date: date
    payment_method: Literal["BANK_TRANSFER", "CASH", "CHEQUE", "CREDIT_CARD", "PETTY_CASH", "OTHER"] = "BANK_TRANSFER"
    currency: str = Field(default="IDR", min_length=3, max_length=3)
    total_amount: Decimal = Field(gt=0)
    reference_number: str | None = None
    cheque_number: str | None = None
    notes: str | None = None
    source_type: Literal["LIVE", "HISTORICAL_IMPORT"] = "LIVE"
    allocations: list[PaymentAllocationInput]
    funding_lines: list[PaymentFundingInput]

    @model_validator(mode="after")
    def validate_totals(self):
        if not self.allocations:
            raise ValueError("Payment requires at least one invoice allocation")
        if not self.funding_lines:
            raise ValueError("Payment requires at least one funding line")
        if len({x.supplier_invoice_id for x in self.allocations}) != len(self.allocations):
            raise ValueError("Duplicate invoice allocation")
        if sum((x.allocated_amount for x in self.allocations), Decimal("0")) != self.total_amount:
            raise ValueError("Invoice allocations must equal payment total")
        if sum((x.amount for x in self.funding_lines), Decimal("0")) != self.total_amount:
            raise ValueError("Funding lines must equal payment total")
        return self


class PaymentUpdate(PaymentCreate):
    pass


class PaymentResponse(BaseModel):
    id: int
    payment_number: str
    payment_date: date
    amount: Decimal
    payment_method: str
    status: str

    class Config:
        from_attributes = True
