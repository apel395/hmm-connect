from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.models.fiscal_period import FiscalPeriod


class FiscalPeriodService:

    @staticmethod
    def business_today() -> date:
        return datetime.now(ZoneInfo("Asia/Jakarta")).date()

    @staticmethod
    def validate_posting_date(
        db: Session,
        posting_date: date,
        system_closing: bool = False,
    ) -> FiscalPeriod | None:

        if not inspect(db.connection()).has_table(FiscalPeriod.__tablename__):
            return None

        period = (
            db.query(FiscalPeriod)
            .filter(
                FiscalPeriod.start_date <= posting_date,
                FiscalPeriod.end_date >= posting_date,
            )
            .populate_existing()
            .with_for_update()
            .first()
        )

        # Posting is governed by the period containing the selected date.
        # An open later month must not silently reopen a closed earlier month.
        if period and period.is_open and not period.is_closed:
            if not system_closing and posting_date < FiscalPeriodService.business_today() and not period.allow_backdated_entries:
                raise HTTPException(
                    status_code=400,
                    detail=f"Backdated entries are disabled for {period.period_name}. Enable them in Accounting Periods.",
                )
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
