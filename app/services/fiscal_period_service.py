from datetime import date

from fastapi import HTTPException
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.models.fiscal_period import FiscalPeriod


class FiscalPeriodService:

    @staticmethod
    def validate_posting_date(
        db: Session,
        posting_date: date,
    ) -> FiscalPeriod | None:

        if not inspect(db.get_bind()).has_table(FiscalPeriod.__tablename__):
            return None

        period = (
            db.query(FiscalPeriod)
            .filter(
                FiscalPeriod.start_date <= posting_date,
                FiscalPeriod.end_date >= posting_date,
            )
            .first()
        )

        if not period:
            raise HTTPException(
                status_code=400,
                detail="No fiscal period found for posting date.",
            )

        if not period.is_open:
            raise HTTPException(
                status_code=400,
                detail=f"Fiscal period {period.period_name} is closed.",
            )

        return period
