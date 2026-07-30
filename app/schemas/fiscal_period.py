from datetime import date

from pydantic import BaseModel


class FiscalPeriodResponse(BaseModel):

    id: int
    fiscal_year: int
    fiscal_month: int
    period_name: str
    start_date: date
    end_date: date
    is_open: bool
    is_closed: bool

    class Config:
        from_attributes = True


class FiscalPeriodCreate(BaseModel):

    fiscal_year: int
    fiscal_month: int
    period_name: str
    start_date: date
    end_date: date
