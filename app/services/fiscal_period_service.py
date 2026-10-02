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

        # Posting is governed by the period containing the selected date.
        # An open later month must not silently reopen a closed earlier month.
        if period and period.is_open and not period.is_closed:
            return period

        if period:
            raise HTTPException(
                status_code=400,
                detail=f"Fiscal period {period.period_name} is closed. Reopen it with a reason before posting.",
            )

        raise HTTPException(
            status_code=400,
            detail=(
                f"No open accounting period covers {posting_date.isoformat()}. "
                "Open a Finance accounting period before posting this date."
            ),
        )
