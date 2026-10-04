from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.v1.fiscal_periods import posting_status
from app.models.fiscal_period import FiscalPeriod
from app.services.fiscal_period_service import FiscalPeriodService


def test_only_the_selected_dates_open_period_allows_posting():
    engine = create_engine("sqlite:///:memory:")
    FiscalPeriod.__table__.create(engine)
    with Session(engine) as db:
        db.add_all([
            FiscalPeriod(fiscal_year=2026, fiscal_month=1, period_name="January 2026",
                         start_date=date(2026, 1, 1), end_date=date(2026, 1, 31),
                         is_open=True, is_closed=False),
            FiscalPeriod(fiscal_year=2026, fiscal_month=2, period_name="February 2026",
                         start_date=date(2026, 2, 1), end_date=date(2026, 2, 28),
                         is_open=False, is_closed=True),
            FiscalPeriod(fiscal_year=2026, fiscal_month=3, period_name="March 2026",
                         start_date=date(2026, 3, 1), end_date=date(2026, 3, 31),
                         is_open=True, is_closed=False),
        ])
        db.commit()

        assert FiscalPeriodService.validate_posting_date(db, date(2026, 1, 8)).fiscal_month == 1
        assert FiscalPeriodService.validate_posting_date(db, date(2026, 3, 8)).fiscal_month == 3
        with pytest.raises(HTTPException, match="February 2026 is closed"):
            FiscalPeriodService.validate_posting_date(db, date(2026, 2, 8))
        with pytest.raises(HTTPException, match="No open accounting period covers"):
            FiscalPeriodService.validate_posting_date(db, date(2026, 4, 8))

        status = posting_status(posting_date=date(2026, 2, 8), db=db, current_user=object())
        assert status["configured"] is True
        assert status["can_post"] is False
        assert status["period_name"] == "February 2026"

def test_open_period_backdate_setting_is_enforced(monkeypatch):
    monkeypatch.setattr(FiscalPeriodService, "business_today", staticmethod(lambda: date(2026, 1, 20)))
    engine = create_engine("sqlite:///:memory:")
    FiscalPeriod.__table__.create(engine)
    with Session(engine) as db:
        period = FiscalPeriod(
            fiscal_year=2026, fiscal_month=1, period_name="January 2026",
            start_date=date(2026, 1, 1), end_date=date(2026, 1, 31),
            is_open=True, is_closed=False, allow_backdated_entries=False,
        )
        db.add(period)
        db.commit()
        with pytest.raises(HTTPException, match="Backdated entries are disabled"):
            FiscalPeriodService.validate_posting_date(db, date(2026, 1, 8))
        assert posting_status(posting_date=date(2026, 1, 8), db=db, current_user=object())["can_post"] is False
        assert FiscalPeriodService.validate_posting_date(db, date(2026, 1, 20)) == period
        period.allow_backdated_entries = True
        db.commit()
        assert FiscalPeriodService.validate_posting_date(db, date(2026, 1, 8)) == period
        assert posting_status(posting_date=date(2026, 1, 8), db=db, current_user=object())["can_post"] is True
        period.is_closed = True
        db.commit()
        with pytest.raises(HTTPException, match="January 2026 is closed"):
            FiscalPeriodService.validate_posting_date(db, date(2026, 1, 8))
