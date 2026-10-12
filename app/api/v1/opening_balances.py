from io import BytesIO
from fastapi.responses import StreamingResponse
from app.services.xlsx_export import build_xlsx
from app.services.organization_access import resolve_organization_access
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import require_permission
from app.services.opening_balance_service import OpeningBalanceService
from app.services.location_access import enforce_location_access, resolve_location_id


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
    location_id = resolve_location_id(user, location_id)
    return OpeningBalanceService(db).accounts(fiscal_year=fiscal_year, location_id=location_id)


@router.get("/export")
def export_excel(
    fiscal_year: int = Query(..., ge=1900, le=9999),
    location_id: int | None = None,
    db: Session = Depends(get_db),
    user=Depends(journal_view_user),
):
    scope = resolve_organization_access(db, user, location_id=location_id)
    data = OpeningBalanceService(db).accounts(
        fiscal_year=fiscal_year, location_id=scope["location_id"],
        business_unit_id=scope["business_unit_id"],
    )
    rows = [[f"Opening balances {fiscal_year}"],
            ["Account code", "Account name", "Type", "Normal balance", "Debit", "Credit"]]
    rows.extend([
        item["account_code"], item["account_name"], item["account_type"],
        item["normal_balance"], item["existing_debit"], item["existing_credit"],
    ] for item in data["items"])
    return StreamingResponse(
        BytesIO(build_xlsx([("Opening balances", rows)])),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="opening-balances-{fiscal_year}.xlsx"'},
    )


@router.get("")
def list_entries(
    fiscal_year: int = Query(...),
    location_id: int | None = None,
    db: Session = Depends(get_db),
    user=Depends(journal_view_user),
):
    location_id = resolve_location_id(user, location_id)
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
    location_id = resolve_location_id(user, location_id)
    return OpeningBalanceService(db).void(
        user=user, fiscal_year=fiscal_year, location_id=location_id
    )
