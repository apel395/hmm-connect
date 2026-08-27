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

router=APIRouter(prefix="/profit-loss",tags=["Financial Reports"])
def access(user):
    if not has_permission(user,"finance.view"):raise HTTPException(403,"Finance report access required")
def serialize(value):
    if isinstance(value,Decimal):return f"{value:.2f}"
    if isinstance(value,date):return value.isoformat()
    if isinstance(value,dict):return {key:serialize(item) for key,item in value.items()}
    if isinstance(value,list):return [serialize(item) for item in value]
    return value
def build(db,date_from,date_to,comparative_date_from,comparative_date_to,account_id,parent_account_id,location_id,department_id,include_zero_balance,include_inactive,detail_level,business_unit_id=None):
    try:return FinancialStatementService(db).profit_and_loss(date_from=date_from,date_to=date_to,comparative_date_from=comparative_date_from,comparative_date_to=comparative_date_to,account_id=account_id,parent_account_id=parent_account_id,location_id=location_id,department_id=department_id,business_unit_id=business_unit_id,include_zero_balance=include_zero_balance,include_inactive=include_inactive,detail_level=detail_level)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
@router.get("")
def get_profit_loss(date_from:date,date_to:date,comparative_date_from:date|None=None,comparative_date_to:date|None=None,account_id:int|None=None,parent_account_id:int|None=None,location_id:int|None=None,department_id:int|None=None,business_unit_id:int|None=None,include_zero_balance:bool=False,include_inactive:bool=False,detail_level:str=Query("DETAIL",pattern="^(SUMMARY|DETAIL)$"),db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);location_id=resolve_location_id(user,location_id);return serialize(build(db,date_from,date_to,comparative_date_from,comparative_date_to,account_id,parent_account_id,location_id,department_id,include_zero_balance,include_inactive,detail_level,business_unit_id))
@router.get("/export")
def export_profit_loss(date_from:date,date_to:date,format:str=Query("xlsx",pattern="^(xlsx|csv)$"),comparative_date_from:date|None=None,comparative_date_to:date|None=None,account_id:int|None=None,parent_account_id:int|None=None,location_id:int|None=None,department_id:int|None=None,include_zero_balance:bool=False,include_inactive:bool=False,detail_level:str=Query("DETAIL",pattern="^(SUMMARY|DETAIL)$"),db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);location_id=resolve_location_id(user,location_id);report=build(db,date_from,date_to,comparative_date_from,comparative_date_to,account_id,parent_account_id,location_id,department_id,include_zero_balance,include_inactive,"DETAIL");s=report["summary"]
    filters=f"Account={account_id or 'All'}; Parent={parent_account_id or 'All'}; Location={location_id or 'All'}; Department={department_id or 'All'}; Include inactive={include_inactive}"
    summary=[("Total Revenue",s["total_revenue"]),("Cost of Revenue",s["cost_of_revenue"]),("Gross Profit",s["gross_profit"]),("Operating Profit",s["operating_profit"]),("Net Profit",s["net_profit_after_tax"])]
    return export_statement(report,"Profit & Loss",f"{date_from} to {date_to}"+(f" compared with {comparative_date_from} to {comparative_date_to}" if comparative_date_from else ""),filters,format,f"profit-loss-{date_from}-{date_to}",summary)
