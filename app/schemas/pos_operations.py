from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field, field_validator

class OutletContext(BaseModel):
    location_id: int = Field(gt=0)
    department_id: int = Field(gt=0)

class OutletPolicyIn(OutletContext):
    order_mode: Literal['TABLE','COUNTER','EVENT']

class TableIn(OutletContext):
    name: str = Field(min_length=1, max_length=30)
    seats: int = Field(default=2, ge=1, le=1000)
    is_active: bool = True
    @field_validator('name')
    @classmethod
    def trim(cls, value):
        value = ' '.join(value.split())
        if not value: raise ValueError('Table name is required')
        return value

class ShiftOpen(OutletContext):
    opening_cash: Decimal = Field(ge=0, max_digits=18, decimal_places=2)

class ShiftClose(BaseModel):
    counted_cash: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    difference_reason: str | None = Field(default=None, max_length=1000)
