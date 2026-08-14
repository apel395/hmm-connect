from datetime import date
from decimal import Decimal
from pydantic import BaseModel,Field
class BudgetLineInput(BaseModel):
    account_id: int
    business_unit_id: int
    location_id: int | None = None
    department_id: int | None = None
    month: int = Field(ge=1, le=12)
    budget_amount: Decimal = Field(ge=0)
    notes: str | None = None

class BudgetCreate(BaseModel):
    name: str = Field(min_length=1)
    fiscal_year: int
    date_from: date
    date_to: date
    currency: str = "IDR"
    description: str | None = None
    lines: list[BudgetLineInput] = Field(min_length=1)
class BudgetUpdate(BaseModel):name:str|None=None;date_from:date|None=None;date_to:date|None=None;currency:str|None=None;description:str|None=None;lines:list[BudgetLineInput]|None=None
class RejectInput(BaseModel):reason:str|None=None
