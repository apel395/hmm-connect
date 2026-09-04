from datetime import date
from decimal import Decimal
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_permission
from app.services.financial_statement_service import FinancialStatementService
from app.services.financial_report_export import export_statement
from app.services.location_access import resolve_location_id

router=APIRouter(prefix="/balance-sheet",tags=["Financial Reports"])
def access(user):
    if not has_permission(user, "finance.view"):raise HTTPException(403,"Finance report access required")
def serialize(value):
    if isinstance(value,Decimal):return f"{value:.2f}"
    if isinstance(value,date):return value.isoformat()
    if isinstance(value,dict):return {key:serialize(item) for key,item in value.items()}
    if isinstance(value,list):return [serialize(item) for item in value]
    return value
def build(db,as_of_date,comparative_date,account_id,parent_account_id,location_id,department_id,include_zero_balance,include_inactive,detail_level,business_unit_id=None,fiscal_year=None):
    return FinancialStatementService(db).balance_sheet(as_of_date=as_of_date,comparative_date=comparative_date,fiscal_year=fiscal_year,account_id=account_id,parent_account_id=parent_account_id,location_id=location_id,department_id=department_id,business_unit_id=business_unit_id,include_zero_balance=include_zero_balance,include_inactive=include_inactive,detail_level=detail_level)
@router.get("")
def get_balance_sheet(as_of_date:date|None=None,comparative_date:date|None=None,fiscal_year:int|None=None,account_id:int|None=None,parent_account_id:int|None=None,location_id:int|None=None,department_id:int|None=None,business_unit_id:int|None=None,include_zero_balance:bool=False,include_inactive:bool=False,detail_level:str=Query("DETAIL",pattern="^(SUMMARY|DETAIL)$"),db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);location_id=resolve_location_id(user,location_id);return serialize(build(db,as_of_date,comparative_date,account_id,parent_account_id,location_id,department_id,include_zero_balance,include_inactive,detail_level,business_unit_id,fiscal_year))
@router.get("/export")
def export_balance_sheet(as_of_date:date|None=None,comparative_date:date|None=None,fiscal_year:int|None=None,format:str=Query("xlsx",pattern="^(xlsx|csv)$"),account_id:int|None=None,parent_account_id:int|None=None,location_id:int|None=None,department_id:int|None=None,include_zero_balance:bool=False,include_inactive:bool=False,detail_level:str=Query("DETAIL",pattern="^(SUMMARY|DETAIL)$"),db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);location_id=resolve_location_id(user,location_id);report=build(db,as_of_date,comparative_date,account_id,parent_account_id,location_id,department_id,include_zero_balance,include_inactive,"DETAIL",business_unit_id=None,fiscal_year=fiscal_year);s=report["summary"]
    filters=f"Fiscal Year={report.get('fiscal_year')}; Account={account_id or 'All'}; Parent={parent_account_id or 'All'}; Location={location_id or 'All'}; Department={department_id or 'All'}; Include inactive={include_inactive}"
    summary=[("Opening Total Assets",s["opening_total_assets"]),("Opening Total Liabilities",s["opening_total_liabilities"]),("Opening Total Equity",s["opening_total_equity"]),("Opening Liabilities + Equity",s["opening_total_liabilities_and_equity"]),("Opening Difference",s["opening_difference"]),("Total Assets",s["total_assets"]),("Total Liabilities",s["total_liabilities"]),("Total Equity",s["total_equity"]),("Liabilities + Equity",s["total_liabilities_and_equity"]),("Difference",s["difference"])]
    return export_statement(report,"Balance Sheet",f"Fiscal Year {report.get('fiscal_year')} (Opening {report['metadata'].get('year_start')} - Closing {report['metadata'].get('year_end')})",filters,format,f"balance-sheet-fiscal-year-{report.get('fiscal_year')}",summary)
