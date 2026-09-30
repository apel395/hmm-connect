from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import require_permission
from app.services.opening_balance_service import OpeningBalanceService
from app.services.location_access import enforce_location_access


router = APIRouter(prefix="/opening-balances", tags=["Opening Balances"])

journal_view_user = require_permission("journal.view")
journal_manage_user = require_permission("journal.manage")


class OpeningLine(BaseModel):
    account_id: int
    amount: float = Field(ge=0)
    balance_type: str | None = None


class OpeningBalanceSubmit(BaseModel):
    fiscal_year: int
    location_id: int | None = None
    description: str | None = None
    lines: list[OpeningLine]


class OpeningBalanceRevision(OpeningBalanceSubmit):
    expected_version: str


@router.get("/accounts")
def accounts(
    fiscal_year: int = Query(...),
    location_id: int | None = None,
    db: Session = Depends(get_db),
    user=Depends(journal_view_user),
):
    if location_id:
        enforce_location_access(user, location_id)
    return OpeningBalanceService(db).accounts(fiscal_year=fiscal_year, location_id=location_id)


@router.get("")
def list_entries(
    fiscal_year: int = Query(...),
    location_id: int | None = None,
    db: Session = Depends(get_db),
    user=Depends(journal_view_user),
):
    if location_id:
        enforce_location_access(user, location_id)
    return OpeningBalanceService(db).list_entries(
        fiscal_year=fiscal_year, location_id=location_id
    )


@router.post("/preview")
def preview(
    data: OpeningBalanceSubmit,
    db: Session = Depends(get_db),
    user=Depends(journal_manage_user),
):
    return OpeningBalanceService(db).prepare(
        fiscal_year=data.fiscal_year,
        lines=[line.model_dump() for line in data.lines],
    )


@router.post("")
def submit(
    data: OpeningBalanceSubmit,
    db: Session = Depends(get_db),
    user=Depends(journal_manage_user),
):
    if data.location_id:
        enforce_location_access(user, data.location_id)
    return OpeningBalanceService(db).post(
        user=user,
        fiscal_year=data.fiscal_year,
        location_id=data.location_id,
        lines=[line.model_dump() for line in data.lines],
        description=data.description,
    )


@router.put("")
def revise(
    data: OpeningBalanceRevision,
    db: Session = Depends(get_db),
    user=Depends(journal_manage_user),
):
    if data.location_id:
        enforce_location_access(user, data.location_id)
    return OpeningBalanceService(db).revise(
        user=user,
        fiscal_year=data.fiscal_year,
        location_id=data.location_id,
        lines=[line.model_dump() for line in data.lines],
        description=data.description,
        expected_version=data.expected_version,
    )


@router.delete("")
def void(
    fiscal_year: int = Query(...),
    location_id: int | None = None,
    db: Session = Depends(get_db),
    user=Depends(journal_manage_user),
):
    if location_id:
        enforce_location_access(user, location_id)
    return OpeningBalanceService(db).void(
        user=user, fiscal_year=fiscal_year, location_id=location_id
    )
