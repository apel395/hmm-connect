from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class AmortizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    category: str | None = Field(default=None, max_length=100)
    description: str | None = None
    start_date: date
    original_cost: Decimal = Field(gt=0)
    useful_life_months: int = Field(gt=0)
    business_unit_id: int
    location_id: int | None = None
    department_id: int | None = None
    asset_account_id: int
    accumulated_amortization_account_id: int
    amortization_expense_account_id: int
    notes: str | None = None


class AmortizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=180)
    category: str | None = Field(default=None, max_length=100)
    description: str | None = None
    business_unit_id: int | None = None
    location_id: int | None = None
    department_id: int | None = None
    notes: str | None = None
