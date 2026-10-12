from datetime import date
from decimal import Decimal
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from app.services.xlsx_export import build_xlsx
from app.services.profit_loss_delivery import CATEGORIES, SETTING_PREFIX, deliver, workbook_sheets
from pydantic import BaseModel, Field
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.authorization import require_permission
from app.models.accounting_setting import AccountingSetting
from app.models.chart_of_account import ChartOfAccount
from app.models.financial_report_setting import FinancialReportSetting
from app.services.audit import record_audit
from app.services.financial_reporting_service import FinancialReportingService
from app.services.location_access import resolve_location_id
from app.services.organization_access import resolve_organization_access
from app.api.v1.profit_loss import serialize

router = APIRouter(prefix="/financial-reports", tags=["Financial Reports"])
view = require_permission("finance.view")
manage = require_permission("finance.manage")
METRIC_NAMES = ("current", "budget", "last_month", "last_year", "variance")
TYPES = "^(PROFIT_LOSS|BALANCE_SHEET)$"


def require_report_setup(db: Session):
    if not inspect(db.connection()).has_table("financial_report_settings"):
        raise HTTPException(503, "Report setup is awaiting a database update. Accounting reports remain available.")


class ReportSetupInput(BaseModel):
    selected_account_ids: list[int] | None = None
    profit_loss_categories: dict[int, str] | None = None
    header_only: bool = False
    current_year_earnings_account_id: int | None = None


@router.get("/setup")
def setup(db: Session = Depends(get_db), user=Depends(view)):
    require_report_setup(db)
    rows = db.query(ChartOfAccount).filter(ChartOfAccount.is_active.is_(True)).order_by(ChartOfAccount.account_number).all()
    settings = db.query(FinancialReportSetting).all()
    earnings = db.query(AccountingSetting).filter_by(setting_key="CURRENT_YEAR_EARNINGS_ACCOUNT").first()
    categories = {row.account_id: row.description for row in db.query(AccountingSetting).filter(AccountingSetting.setting_key.startswith(SETTING_PREFIX)).all()}
    return {"profit_loss_categories": categories, "category_options": CATEGORIES, "accounts": [{"id": a.id, "code": a.account_number, "name": a.account_name,
             "type": a.account_type, "normal_balance": a.normal_balance, "parent_id": a.parent_account_id, "is_posting": a.is_posting} for a in rows],
            "settings": [{"report_type": s.report_type, "selected_account_ids": s.selected_account_ids, "header_only": s.header_only} for s in settings],
            "current_year_earnings_account_id": earnings.account_id if earnings else None}


@router.put("/setup/{report_type}")
def save_setup(data: ReportSetupInput, report_type: str, db: Session = Depends(get_db), user=Depends(manage)):
    require_report_setup(db)
    if report_type not in ("PROFIT_LOSS", "BALANCE_SHEET"):
        raise HTTPException(422, "Unsupported report type")
    if data.selected_account_ids is not None:
        ids = set(data.selected_account_ids)
        allowed = ("REVENUE", "INCOME", "EXPENSE") if report_type == "PROFIT_LOSS" else ("ASSET", "LIABILITY", "EQUITY")
        found = db.query(ChartOfAccount.id).filter(ChartOfAccount.id.in_(ids), ChartOfAccount.account_type.in_(allowed)).all()
        if len(found) != len(ids):
            raise HTTPException(422, "Selected accounts do not belong to this report")
    if data.current_year_earnings_account_id is not None:
        account = db.get(ChartOfAccount, data.current_year_earnings_account_id)
        if not account or not account.is_active or not account.is_posting or account.account_type != "EQUITY" or account.normal_balance != "CREDIT":
            raise HTTPException(422, "Current-year earnings requires an active credit equity account")
        mapping = db.query(AccountingSetting).filter_by(setting_key="CURRENT_YEAR_EARNINGS_ACCOUNT").first()
        if not mapping:
            mapping = AccountingSetting(setting_key="CURRENT_YEAR_EARNINGS_ACCOUNT")
            db.add(mapping)
        mapping.account_id = account.id
    previous_categories = {row.account_id: row.description for row in db.query(AccountingSetting).filter(AccountingSetting.setting_key.startswith(SETTING_PREFIX)).all()}
    if data.profit_loss_categories is not None:
        if report_type != "PROFIT_LOSS":
            raise HTTPException(422, "P&L categories apply only to Profit & Loss")
        for aid, code in data.profit_loss_categories.items():
            account = db.get(ChartOfAccount, aid)
            if not account or not account.is_posting or account.account_type != "EXPENSE" or code not in CATEGORIES or code == "REVENUE":
                raise HTTPException(422, "Choose a valid expense account and P&L category")
        existing = db.query(AccountingSetting).filter(AccountingSetting.setting_key.startswith(SETTING_PREFIX)).with_for_update().all()
        for mapping in existing:
            if mapping.account_id not in data.profit_loss_categories:
                db.delete(mapping)
        by_id = {row.account_id: row for row in existing}
        for aid, code in data.profit_loss_categories.items():
            mapping = by_id.get(aid)
            if not mapping:
                mapping = AccountingSetting(setting_key=f"{SETTING_PREFIX}{aid}", account_id=aid)
                db.add(mapping)
            mapping.description = code
    setting = db.query(FinancialReportSetting).filter_by(report_type=report_type).with_for_update().first()
    if not setting:
        setting = FinancialReportSetting(report_type=report_type)
        db.add(setting)
    before = {"selected_account_ids": setting.selected_account_ids, "header_only": setting.header_only, "profit_loss_categories": previous_categories}
    setting.selected_account_ids = sorted(set(data.selected_account_ids)) if data.selected_account_ids is not None else None
    setting.header_only, setting.updated_by_id = data.header_only, user.id
    record_audit(db, user, "FINANCIAL_REPORT_SETUP_UPDATED", "FINANCIAL_REPORT", f"Updated {report_type} display",
                 before_data=before, after_data=data.model_dump())
    db.commit()
    return {"message": "Report setup saved"}


@router.get("/comparison")
def comparison(report_type: str = Query(pattern=TYPES), as_of_date: date = Query(),
               location_id: int | None = None, business_unit_id: int | None = None,
               department_id: int | None = None, budget_id: int | None = None,
               kap: bool = False, include_zero: bool = False, detail: bool = False,
               department_tables: bool = False,
               report_scope: str | None = None,
               db: Session = Depends(get_db), user=Depends(view)):
    allowed = resolve_organization_access(db, user, location_id=location_id, business_unit_id=business_unit_id, department_id=department_id)
    scope, business_unit_id, department_id = allowed["location_id"], allowed["business_unit_id"], allowed["department_id"]
    service = FinancialReportingService(db)
    if report_type == "PROFIT_LOSS" and report_scope is not None:
        report = deliver(service, as_of_date=as_of_date, report_scope=report_scope, location_id=scope,
                         business_unit_id=business_unit_id, department_id=department_id, budget_id=budget_id,
                         kap=kap, include_zero=include_zero, detail=detail, include_breakdown=False)
        return serialize(report)
    report = service.build(report_type=report_type, as_of_date=as_of_date,
        location_id=scope, business_unit_id=business_unit_id, department_id=department_id,
        budget_id=budget_id, kap=kap, include_zero=include_zero, detail=detail)
    if report_type == "PROFIT_LOSS" and not department_tables:
        from app.services.management_dashboard import activity_rows, departments
        report["departments"] = departments(db, activity_rows(db, as_of_date, report["scope"]), as_of_date.month, report["scope"])
    if report_type == "PROFIT_LOSS" and department_tables:
        report["department_reports"] = service.department_reports(report, budget_id=budget_id, kap=kap, include_zero=include_zero, detail=detail)
    return serialize(report)


@router.get("/comparison/export")
def export_comparison(report_type: str = Query(pattern=TYPES), as_of_date: date = Query(),
                      location_id: int | None = None, business_unit_id: int | None = None,
                      department_id: int | None = None, budget_id: int | None = None,
                      kap: bool = False, include_zero: bool = False, detail: bool = False,
               department_tables: bool = False,
               report_scope: str | None = None,
                      db: Session = Depends(get_db), user=Depends(view)):
    allowed = resolve_organization_access(db, user, location_id=location_id, business_unit_id=business_unit_id, department_id=department_id)
    scope, business_unit_id, department_id = allowed["location_id"], allowed["business_unit_id"], allowed["department_id"]
    service = FinancialReportingService(db)
    if report_type == "PROFIT_LOSS" and report_scope is not None:
        report = deliver(service, as_of_date=as_of_date, report_scope=report_scope, location_id=scope,
                         business_unit_id=business_unit_id, department_id=department_id, budget_id=budget_id,
                         kap=False, include_zero=include_zero, detail=True)
        output = BytesIO(build_xlsx(workbook_sheets(report)))
        return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="profit_loss-{report_scope.lower()}-{as_of_date}.xlsx"'})
    report = service.build(report_type=report_type, as_of_date=as_of_date,
        location_id=scope, business_unit_id=business_unit_id, department_id=department_id,
        budget_id=budget_id, kap=kap, include_zero=include_zero, detail=detail)
    sheets = []
    for period in ("MTD", "YTD"):
        rows = []
        labels = report["scope_labels"]
        rows.append([report_type, as_of_date.isoformat(), "Location", labels["location_id"], "Unit", labels["business_unit_id"], "Department", labels["department_id"]])
        metrics = ("current", "budget", "last_month", "last_year", "variance") + (("movement",) if report_type == "BALANCE_SHEET" else ())
        rows.append(["Name", "Current", "Budget", "Last month", "Same period last year", "Variance"] + (["Period movement"] if report_type == "BALANCE_SHEET" else []))
        for section, totals in report["section_totals"].items():
            values = totals[period]
            rows.append([section, *[values[m] if values[m] is not None else None for m in metrics]])
            for row in report["rows"]:
                if row["section"] != section:
                    continue
                values = row["periods"][period]
                rows.append([row["account_name"], *[values[m] if values[m] is not None else None for m in metrics]])
        if report_type == "PROFIT_LOSS":
            v = report["section_totals"]
            rows.append(["Net profit", *[None if any(v[s][period][m] is None for s in v) else v["REVENUE"][period][m] - v["COST_OF_REVENUE"][period][m] - v["EXPENSES"][period][m] for m in metrics]])
            if not department_tables:
                from app.services.management_dashboard import activity_rows, departments
                rows.append([])
                rows.append(["Department", "Revenue", "Cost of revenue", "Operating expenses", "Other expenses", "Profit / loss"])
                for department in departments(db, activity_rows(db, as_of_date, report["scope"]), as_of_date.month, report["scope"]):
                    values = department[period]
                    rows.append([department["department_name"], *[values[key] for key in ("revenue", "cogs", "operating_expenses", "other_expenses", "nop")]])
        sheets.append((period, rows))
    if report_type == "PROFIT_LOSS" and department_tables:
        for index, department in enumerate(service.department_reports(report, budget_id=budget_id, kap=kap, include_zero=include_zero, detail=detail), 1):
            for period in ("MTD", "YTD"):
                rows = [[department["department_name"], period, as_of_date.isoformat()],
                        ["Name", "Current", "Budget", "Last month", "Last year", "Variance"]]
                for section, totals in department["section_totals"].items():
                    rows.append([section, *[totals[period][m] for m in METRIC_NAMES]])
                    rows += [[row["account_name"], *[row["periods"][period][m] for m in METRIC_NAMES]] for row in department["rows"] if row["section"] == section]
                v = department["section_totals"]
                rows.append(["Net profit", *[None if any(v[section][period][m] is None for section in v) else v["REVENUE"][period][m]-v["COST_OF_REVENUE"][period][m]-v["EXPENSES"][period][m] for m in METRIC_NAMES]])
                sheets.append((f"D{index} {period}", rows))
    output = BytesIO(build_xlsx(sheets))
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{report_type.lower()}-{as_of_date}.xlsx"'})
