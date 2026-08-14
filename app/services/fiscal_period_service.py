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
                detail=(
                    f"No fiscal period configured for {posting_date.isoformat()}. "
                    f"Initialize fiscal year {posting_date.year} in Finance > Fiscal Periods before posting."
                ),
            )

        if not period.is_open or period.is_closed:
            raise HTTPException(
                status_code=400,
                detail=f"Fiscal period {period.period_name} is closed. Reopen it with a reason before posting.",
            )

        return period
