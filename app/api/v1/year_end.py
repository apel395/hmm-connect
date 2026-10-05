from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy.orm import Session

from app.core.database import get_db

from app.dependencies.authorization import require_permission

from app.services.year_end_service import YearEndService
from app.services.location_access import assigned_location_id

router = APIRouter(
    prefix="/year-end",
    tags=["Year End"],
)


@router.post("/{year}")
def close_year(
    year: int,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_permission("finance.manage")
    ),
):

    if assigned_location_id(current_user) is not None:
        raise HTTPException(403, "Year closing requires access to all locations")
    journal = YearEndService.close_year(
        db=db,
        fiscal_year=year,
        closing_date=date.today(),
        user=current_user,
    )

    return journal
