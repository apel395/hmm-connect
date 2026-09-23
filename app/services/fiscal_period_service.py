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

        # Finance rule: an OPEN accounting period opens that period and all
        # earlier posting dates. This supports historical finance entry without
        # requiring every older month to be reopened individually.
        latest_open = (
            db.query(FiscalPeriod)
            .filter(
                FiscalPeriod.is_open.is_(True),
                FiscalPeriod.is_closed.is_(False),
                FiscalPeriod.end_date >= posting_date,
            )
            .order_by(FiscalPeriod.end_date.desc())
            .first()
        )

        if latest_open:
            return period or latest_open

        if period:
            raise HTTPException(
                status_code=400,
                detail=f"Fiscal period {period.period_name} is closed. Reopen it with a reason before posting.",
            )

        raise HTTPException(
            status_code=400,
            detail=(
                f"No open accounting period covers or follows {posting_date.isoformat()}. "
                "Open a Finance accounting period before posting this date."
            ),
        )
