import csv
from datetime import date
from io import StringIO

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_any_role
from app.services.trial_balance_service import TrialBalanceService

router = APIRouter(prefix="/trial-balance", tags=["Financial Reports"])
MONEY_FIELDS = (
    "opening_balance",
    "period_debit",
    "period_credit",
    "period_total",
    "closing_balance",
)


def access(user):
    if not has_any_role(user, "FINANCE", "GENERAL_MANAGER", "AUDITOR", "VIEWER"):
        raise HTTPException(403, "Finance report access required")


def serialize(report: dict) -> dict:
    for row in report["items"]:
        for field in MONEY_FIELDS:
            row[field] = f"{row[field]:.2f}"
        # Compatibility values remain numeric internally but are normalized for legacy UI consumers.
        for field in ("opening_debit", "opening_credit", "closing_debit", "closing_credit"):
            if field in row:
                row[field] = f"{row[field]:.2f}"
    for field in (*MONEY_FIELDS, "opening_debit", "opening_credit", "closing_debit", "closing_credit", "difference"):
        if field in report["summary"]:
            report["summary"][field] = f"{report['summary'][field]:.2f}"
    return report


def build_report(
    db,
    date_from,
    date_to,
    page,
    page_size,
    search,
    account_type,
    account_id,
    parent_account_id,
    include_zero_balance,
    include_inactive,
    location_id,
    department_id,
    business_unit_id,
    sort_by,
    sort_order,
    paginate=True,
):
    try:
        return TrialBalanceService(db).report(
            date_from=date_from,
            date_to=date_to,
            page=page,
            page_size=page_size,
            search=search,
            account_type=account_type,
            account_id=account_id,
            parent_account_id=parent_account_id,
            include_zero_balance=include_zero_balance,
            include_inactive=include_inactive,
            location_id=location_id,
            department_id=department_id,
            business_unit_id=business_unit_id,
            sort_by=sort_by,
            sort_order=sort_order,
            paginate=paginate,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("")
def get_trial_balance(
    date_from: date,
    date_to: date,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: str | None = None,
    account_type: str | None = None,
    account_id: int | None = None,
    parent_account_id: int | None = None,
    include_zero_balance: bool = False,
    include_inactive: bool = False,
    location_id: int | None = None,
    department_id: int | None = None,
    business_unit_id: int | None = None,
    sort_by: str = "account_code",
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    access(user)
    return serialize(build_report(
        db, date_from, date_to, page, page_size, search, account_type, account_id,
        parent_account_id, include_zero_balance, include_inactive, location_id,
        department_id, business_unit_id, sort_by, sort_order,
    ))


@router.get("/export")
def export_trial_balance_csv(
    date_from: date,
    date_to: date,
    search: str | None = None,
    account_type: str | None = None,
    account_id: int | None = None,
    parent_account_id: int | None = None,
    include_zero_balance: bool = False,
    include_inactive: bool = False,
    location_id: int | None = None,
    department_id: int | None = None,
    business_unit_id: int | None = None,
    sort_by: str = "account_code",
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    access(user)
    report = build_report(
        db, date_from, date_to, 1, 200, search, account_type, account_id,
        parent_account_id, include_zero_balance, include_inactive, location_id,
        department_id, business_unit_id, sort_by, sort_order, paginate=False,
    )
    headers = [
        "No COA", "Nama COA", "Opening", "Mutasi Debit", "Mutasi Credit",
        "Total", "Closing", "Status",
    ]
    fields = [
        "account_code", "account_name", "opening_balance", "period_debit",
        "period_credit", "period_total", "closing_balance", "status",
    ]
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in report["items"]:
        writer.writerow([row[field] for field in fields])
    filename = f"trial-balance-{date_from}-{date_to}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
