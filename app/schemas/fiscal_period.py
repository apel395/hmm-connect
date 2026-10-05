from datetime import date

from pydantic import BaseModel, Field


class FiscalPeriodResponse(BaseModel):
    id: int
    fiscal_year: int
    fiscal_month: int
    period_name: str
    start_date: date
    end_date: date
    is_open: bool
    is_closed: bool
    allow_backdated_entries: bool = True
    closing_journal_ids: list[int] = Field(default_factory=list)

    class Config:
        from_attributes = True


class FiscalPeriodCreate(BaseModel):
    fiscal_year: int
    fiscal_month: int
    period_name: str
    start_date: date
    end_date: date


class FiscalYearInitialize(BaseModel):
    fiscal_year: int = Field(ge=2000, le=2100)


class FiscalPeriodReason(BaseModel):
    reason: str = Field(min_length=3, max_length=255)


class FiscalPeriodBackdatePolicy(BaseModel):
    allow_backdated_entries: bool
