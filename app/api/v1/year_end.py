from datetime import date

from fastapi import APIRouter, Depends

from sqlalchemy.orm import Session

from app.core.database import get_db

from app.dependencies.authorization import require_permission

from app.services.year_end_service import YearEndService

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

    journal = YearEndService.close_year(
        db=db,
        fiscal_year=year,
        closing_date=date.today(),
        user=current_user,
    )

    return journal
