from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

TAX_CREDIT_TYPE = Literal["PPh 22", "PPh 23", "PPh 24", "PPh 25", "OTHER"]


class CompanyTaxProfileUpsert(BaseModel):
    npwp: str | None = Field(default=None, max_length=32)
    company_name: str | None = Field(default=None, max_length=250)
    address: str | None = Field(default=None, max_length=500)
    city: str | None = Field(default=None, max_length=100)
    klu: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=150)
    representative_name: str | None = Field(default=None, max_length=150)


class CompanyTaxProfileRead(CompanyTaxProfileUpsert):
    id: int
    tax_year: int
    created_at: datetime
    updated_at: datetime


class TaxCreditCreate(BaseModel):
    tax_year: int
    credit_type: TAX_CREDIT_TYPE
    amount: Decimal = Field(ge=0)
    payment_date: date | None = None
    description: str | None = Field(default=None, max_length=250)
    counterparty_npwp: str | None = Field(default=None, max_length=32)
    counterparty_name: str | None = Field(default=None, max_length=200)


class TaxCreditUpdate(BaseModel):
    credit_type: TAX_CREDIT_TYPE | None = None
    amount: Decimal | None = Field(default=None, ge=0)
    payment_date: date | None = None
    description: str | None = Field(default=None, max_length=250)
    counterparty_npwp: str | None = Field(default=None, max_length=32)
    counterparty_name: str | None = Field(default=None, max_length=200)


class TaxCreditRead(TaxCreditCreate):
    id: int
    created_at: datetime
    updated_at: datetime
