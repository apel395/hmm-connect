from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy.orm import Session

from app.core.database import get_db

from app.dependencies.auth import get_current_user
from app.dependencies.authorization import require_roles

from app.models.fiscal_period import FiscalPeriod

from app.schemas.fiscal_period import (
    FiscalPeriodCreate,
    FiscalPeriodResponse,
)

router = APIRouter(
    prefix="/fiscal-periods",
    tags=["Fiscal Period"],
)


@router.get(
    "",
    response_model=list[FiscalPeriodResponse],
)
def get_periods(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):

    return (
        db.query(FiscalPeriod)
        .order_by(
            FiscalPeriod.fiscal_year.desc(),
            FiscalPeriod.fiscal_month.desc(),
        )
        .all()
    )


@router.post(
    "",
    response_model=FiscalPeriodResponse,
)
def create_period(
    data: FiscalPeriodCreate,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_roles(
            "ADMIN",
            "FINANCE",
        )
    ),
):

    exists = (
        db.query(FiscalPeriod)
        .filter(
            FiscalPeriod.fiscal_year == data.fiscal_year,
            FiscalPeriod.fiscal_month == data.fiscal_month,
        )
        .first()
    )

    if exists:
        raise HTTPException(
            status_code=400,
            detail="Fiscal period already exists.",
        )

    period = FiscalPeriod(
        fiscal_year=data.fiscal_year,
        fiscal_month=data.fiscal_month,
        period_name=data.period_name,
        start_date=data.start_date,
        end_date=data.end_date,
    )

    db.add(period)

    db.commit()

    db.refresh(period)

    return period


@router.post("/{period_id}/close")
def close_period(
    period_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_roles(
            "ADMIN",
            "FINANCE",
        )
    ),
):

    period = (
        db.query(FiscalPeriod)
        .filter(
            FiscalPeriod.id == period_id,
        )
        .first()
    )

    if not period:
        raise HTTPException(
            status_code=404,
            detail="Fiscal period not found.",
        )

    period.is_open = False
    period.is_closed = True
    period.closed_at = date.today()

    db.commit()

    return {
        "message": "Fiscal period closed."
    }


@router.post("/{period_id}/open")
def reopen_period(
    period_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_roles(
            "ADMIN",
            "FINANCE",
        )
    ),
):

    period = (
        db.query(FiscalPeriod)
        .filter(
            FiscalPeriod.id == period_id,
        )
        .first()
    )

    if not period:
        raise HTTPException(
            status_code=404,
            detail="Fiscal period not found.",
        )

    period.is_open = True
    period.is_closed = False
    period.closed_at = None

    db.commit()

    return {
        "message": "Fiscal period reopened."
    }
