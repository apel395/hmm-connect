from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_permission, require_permission
from app.services.fiscal_balance_sheet_service import FiscalBalanceSheetService
from app.services.financial_report_export import export_statement
from app.services.location_access import resolve_location_id

router = APIRouter(prefix="/fiscal-balance-sheet", tags=["Financial Reports"])


def access(user):
    if not has_permission(user, "finance.view"):
        raise HTTPException(403, "Finance report access required")


def serialize(value):
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: serialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [serialize(item) for item in value]
    return value


@router.get("")
def get_fiscal_balance_sheet(
    fiscal_year: int = Query(...),
    location_id: int | None = None,
    department_id: int | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    access(user)
    location_id = resolve_location_id(user, location_id)
    report = FiscalBalanceSheetService(db).report(
        fiscal_year=fiscal_year, location_id=location_id, department_id=department_id
    )
    return serialize(report)


@router.get("/export")
def export_fiscal_balance_sheet(
    fiscal_year: int = Query(...),
    format: str = Query("xlsx", pattern="^(xlsx|csv)$"),
    location_id: int | None = None,
    department_id: int | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    access(user)
    location_id = resolve_location_id(user, location_id)
    report = FiscalBalanceSheetService(db).report(
        fiscal_year=fiscal_year, location_id=location_id, department_id=department_id
    )
    s = report["summary"]
    filters = f"Fiscal Year={fiscal_year}; Basis=PER-11/PJ/2025 Neraca; Location={location_id or 'All'}; Department={department_id or 'All'}"
    summary = [
        ("Total Assets", s["total_assets"]),
        ("Total Liabilities", s["total_liabilities"]),
        ("Total Equity", s["total_equity"]),
        ("Liabilities + Equity", s["total_liabilities_and_equity"]),
        ("Difference", s["difference"]),
    ]
    return export_statement(
        report, "Fiscal Balance Sheet (Coretax Neraca)",
        f"Fiscal Year {fiscal_year} ({report['metadata']['year_start']} - {report['metadata']['year_end']})",
        filters, format, f"fiscal-balance-sheet-{fiscal_year}", summary,
    )
