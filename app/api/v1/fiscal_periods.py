from calendar import month_name, monthrange
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import require_permission
from app.models.fiscal_period import FiscalPeriod
from app.schemas.fiscal_period import (
    FiscalPeriodCreate,
    FiscalPeriodReason,
    FiscalPeriodResponse,
    FiscalYearInitialize,
)
from app.services.audit import record_audit

router = APIRouter(prefix="/fiscal-periods", tags=["Fiscal Period"])
manage_access = require_permission("finance.manage")


@router.get("", response_model=list[FiscalPeriodResponse])
def get_periods(
    fiscal_year: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = db.query(FiscalPeriod)
    if fiscal_year is not None:
        query = query.filter(FiscalPeriod.fiscal_year == fiscal_year)
    return query.order_by(FiscalPeriod.fiscal_year.desc(), FiscalPeriod.fiscal_month.asc()).all()


@router.get("/posting-status")
def posting_status(
    posting_date: date,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    period = db.query(FiscalPeriod).filter(
        FiscalPeriod.start_date <= posting_date,
        FiscalPeriod.end_date >= posting_date,
    ).first()
    if not period:
        return {
            "configured": False,
            "can_post": False,
            "posting_date": posting_date,
            "fiscal_year": posting_date.year,
            "message": f"Fiscal year {posting_date.year} has not been initialized for this posting date.",
        }
    return {
        "configured": True,
        "can_post": bool(period.is_open and not period.is_closed),
        "posting_date": posting_date,
        "period_id": period.id,
        "period_name": period.period_name,
        "fiscal_year": period.fiscal_year,
        "fiscal_month": period.fiscal_month,
        "is_open": period.is_open,
        "is_closed": period.is_closed,
        "message": "Posting period is open." if period.is_open and not period.is_closed else f"Fiscal period {period.period_name} is closed.",
    }


@router.post("/initialize-year")
def initialize_year(
    data: FiscalYearInitialize,
    db: Session = Depends(get_db),
    current_user=Depends(manage_access),
):
    existing_months = {
        row.fiscal_month
        for row in db.query(FiscalPeriod).filter(FiscalPeriod.fiscal_year == data.fiscal_year).all()
    }
    created = []
    for month in range(1, 13):
        if month in existing_months:
            continue
        last_day = monthrange(data.fiscal_year, month)[1]
        period = FiscalPeriod(
            fiscal_year=data.fiscal_year,
            fiscal_month=month,
            period_name=f"{month_name[month]} {data.fiscal_year}",
            start_date=date(data.fiscal_year, month, 1),
            end_date=date(data.fiscal_year, month, last_day),
            is_open=True,
            is_closed=False,
        )
        db.add(period)
        created.append(period)

    record_audit(
        db,
        current_user,
        "FISCAL_YEAR_INITIALIZED",
        "FISCAL_PERIOD",
        f"Initialized fiscal year {data.fiscal_year}; created {len(created)} periods",
        after_data={"fiscal_year": data.fiscal_year, "created_months": [row.fiscal_month for row in created]},
    )
    db.commit()
    return {
        "fiscal_year": data.fiscal_year,
        "created_count": len(created),
        "existing_count": len(existing_months),
        "message": "Fiscal year initialized." if created else "Fiscal year was already initialized.",
    }


@router.post("", response_model=FiscalPeriodResponse)
def create_period(
    data: FiscalPeriodCreate,
    db: Session = Depends(get_db),
    current_user=Depends(manage_access),
):
    exists = db.query(FiscalPeriod).filter(
        FiscalPeriod.fiscal_year == data.fiscal_year,
        FiscalPeriod.fiscal_month == data.fiscal_month,
    ).first()
    if exists:
        raise HTTPException(status_code=400, detail="Fiscal period already exists.")
    if data.end_date < data.start_date:
        raise HTTPException(status_code=422, detail="Fiscal period end date must be on or after start date.")

    period = FiscalPeriod(
        fiscal_year=data.fiscal_year,
        fiscal_month=data.fiscal_month,
        period_name=data.period_name,
        start_date=data.start_date,
        end_date=data.end_date,
    )
    db.add(period)
    db.flush()
    record_audit(db, current_user, "FISCAL_PERIOD_CREATED", "FISCAL_PERIOD", f"Created {period.period_name}", entity_id=period.id)
    db.commit()
    db.refresh(period)
    return period


@router.post("/{period_id}/close")
def close_period(
    period_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(manage_access),
):
    period = db.get(FiscalPeriod, period_id)
    if not period:
        raise HTTPException(status_code=404, detail="Fiscal period not found.")
    if period.is_closed:
        return {"message": "Fiscal period is already closed."}

    period.is_open = False
    period.is_closed = True
    period.closed_at = date.today()
    record_audit(db, current_user, "FISCAL_PERIOD_CLOSED", "FISCAL_PERIOD", f"Closed {period.period_name}", entity_id=period.id)
    db.commit()
    return {"message": "Fiscal period closed."}


@router.post("/{period_id}/open")
def reopen_period(
    period_id: int,
    data: FiscalPeriodReason,
    db: Session = Depends(get_db),
    current_user=Depends(manage_access),
):
    period = db.get(FiscalPeriod, period_id)
    if not period:
        raise HTTPException(status_code=404, detail="Fiscal period not found.")
    if period.is_open and not period.is_closed:
        return {"message": "Fiscal period is already open."}

    period.is_open = True
    period.is_closed = False
    period.closed_at = None
    record_audit(
        db,
        current_user,
        "FISCAL_PERIOD_REOPENED",
        "FISCAL_PERIOD",
        f"Reopened {period.period_name}: {data.reason}",
        entity_id=period.id,
        after_data={"reason": data.reason},
    )
    db.commit()
    return {"message": "Fiscal period reopened."}
