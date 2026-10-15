from datetime import date
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator, model_validator


class StatisticalValueInput(BaseModel):
    account_id: int = Field(gt=0)
    period: date
    location_id: int = Field(gt=0)
    department_id: int | None = Field(default=None, gt=0)
    unit: str = Field(min_length=1, max_length=30)
    actual: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    budget: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    version: int | None = Field(default=None, ge=1)

    @field_validator("unit")
    @classmethod
    def normalize_unit(cls, value):
        value = value.strip().upper()
        if not value:
            raise ValueError("Unit is required")
        return value

    @field_validator("period")
    @classmethod
    def monthly_period(cls, value):
        if value.day != 1 or value.year < 2026:
            raise ValueError("Use the first day of a month from 2026 onward")
        return value

    @model_validator(mode="after")
    def some_value(self):
        if self.actual is None and self.budget is None:
            raise ValueError("Enter Actual or Budget; zero is accepted")
        return self
