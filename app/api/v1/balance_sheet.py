from datetime import date
from decimal import Decimal
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.services.financial_statement_service import FinancialStatementService
from app.services.financial_report_export import export_statement

router=APIRouter(prefix="/balance-sheet",tags=["Financial Reports"])
def access(user):
    if not {role.name for role in user.roles}.intersection({"FINANCE","ADMIN"}):raise HTTPException(403,"Finance report access required")
def serialize(value):
    if isinstance(value,Decimal):return f"{value:.2f}"
    if isinstance(value,date):return value.isoformat()
    if isinstance(value,dict):return {key:serialize(item) for key,item in value.items()}
    if isinstance(value,list):return [serialize(item) for item in value]
    return value
def build(db,as_of_date,comparative_date,account_id,parent_account_id,location_id,department_id,include_zero_balance,include_inactive,detail_level,business_unit_id=None):
    return FinancialStatementService(db).balance_sheet(as_of_date=as_of_date,comparative_date=comparative_date,account_id=account_id,parent_account_id=parent_account_id,location_id=location_id,department_id=department_id,business_unit_id=business_unit_id,include_zero_balance=include_zero_balance,include_inactive=include_inactive,detail_level=detail_level)
@router.get("")
def get_balance_sheet(as_of_date:date,comparative_date:date|None=None,account_id:int|None=None,parent_account_id:int|None=None,location_id:int|None=None,department_id:int|None=None,business_unit_id:int|None=None,include_zero_balance:bool=False,include_inactive:bool=False,detail_level:str=Query("DETAIL",pattern="^(SUMMARY|DETAIL)$"),db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);return serialize(build(db,as_of_date,comparative_date,account_id,parent_account_id,location_id,department_id,include_zero_balance,include_inactive,detail_level,business_unit_id))
@router.get("/export")
def export_balance_sheet(as_of_date:date,format:str=Query("xlsx",pattern="^(xlsx|csv)$"),comparative_date:date|None=None,account_id:int|None=None,parent_account_id:int|None=None,location_id:int|None=None,department_id:int|None=None,include_zero_balance:bool=False,include_inactive:bool=False,detail_level:str=Query("DETAIL",pattern="^(SUMMARY|DETAIL)$"),db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);report=build(db,as_of_date,comparative_date,account_id,parent_account_id,location_id,department_id,include_zero_balance,include_inactive,"DETAIL");s=report["summary"]
    filters=f"Account={account_id or 'All'}; Parent={parent_account_id or 'All'}; Location={location_id or 'All'}; Department={department_id or 'All'}; Include inactive={include_inactive}"
    summary=[("Total Assets",s["total_assets"]),("Total Liabilities",s["total_liabilities"]),("Total Equity",s["total_equity"]),("Liabilities + Equity",s["total_liabilities_and_equity"]),("Difference",s["difference"])]
    return export_statement(report,"Balance Sheet",f"As of {as_of_date}"+(f" compared with {comparative_date}" if comparative_date else ""),filters,format,f"balance-sheet-{as_of_date}",summary)
