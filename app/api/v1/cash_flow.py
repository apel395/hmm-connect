from collections import defaultdict
from datetime import date
from decimal import Decimal
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_permission
from app.services.cash_flow_service import CASH_TYPES,CashFlowService,ZERO
from app.services.location_access import resolve_location_id, require_location_access

router=APIRouter(prefix="/cash-flow",tags=["Cash Flow"])
def access(user):
    if not has_permission(user, "finance.view"):raise HTTPException(403,"Finance access required")
def subtypes(value):return [x.strip().upper() for x in value.split(",") if x.strip()] if value else None

@router.get("")
def legacy(posting_date_from:date|None=None,posting_date_to:date|None=None,db:Session=Depends(get_db),user=Depends(get_current_user)):return statement(posting_date_from,posting_date_to,None,None,db,user)

@router.get("/accounts")
def accounts(date_from:date|None=None,date_to:date|None=None,location_id:int|None=None,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);location_id=resolve_location_id(user,location_id);return CashFlowService(db).accounts_summary(date_from,date_to,location_id)

@router.get("/accounts/{account_id}/activity")
def activity(account_id:int,page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),date_from:date|None=None,date_to:date|None=None,search:str|None=None,direction:str|None=None,reference_type:str|None=None,cash_flow_category:str|None=None,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user)
    location_id=resolve_location_id(user,None)
    try:return CashFlowService(db).activity(account_id,page,page_size,date_from,date_to,search,direction,reference_type,cash_flow_category,location_id=location_id)
    except ValueError as exc:raise HTTPException(404,str(exc)) from exc

@router.get("/summary")
def summary(date_from:date|None=None,date_to:date|None=None,account_id:int|None=None,account_subtype:str|None=None,location_id:int|None=None,department_id:int|None=None,business_unit_id:int|None=None,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);location_id=resolve_location_id(user,location_id);return CashFlowService(db).summary(date_from,date_to,account_id,subtypes(account_subtype),location_id,department_id,business_unit_id)

@router.get("/timeline")
def timeline(date_from:date|None=None,date_to:date|None=None,interval:str=Query("DAILY",pattern="^(DAILY|WEEKLY|MONTHLY)$"),account_id:int|None=None,category:str|None=None,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);location_id=resolve_location_id(user,None);svc=CashFlowService(db);opening=svc.opening(date_from,account_id,location_id=location_id);groups=defaultdict(lambda:{"inflow":ZERO,"outflow":ZERO})
    for m in svc.movements(date_from,date_to,account_id,location_id=location_id):
        if m["direction"]=="TRANSFER" or category and m["category"]!=category:continue
        d=m["date"];period=d.isoformat() if interval=="DAILY" else f"{d.isocalendar().year}-W{d.isocalendar().week:02d}" if interval=="WEEKLY" else d.strftime("%Y-%m");groups[period]["inflow"]+=m["inflow"];groups[period]["outflow"]+=m["outflow"]
    balance=opening;points=[]
    for period,values in sorted(groups.items()):balance+=values["inflow"]-values["outflow"];points.append({"period":period,"inflow":values["inflow"],"outflow":values["outflow"],"net":values["inflow"]-values["outflow"],"closing_balance":balance})
    return {"opening_balance":opening,"items":points}

@router.get("/statement")
def statement(date_from:date|None=None,date_to:date|None=None,account_id:int|None=None,location_id:int|None=None,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);location_id=resolve_location_id(user,location_id);svc=CashFlowService(db);summary_data=svc.summary(date_from,date_to,account_id,location_id=location_id);sections={key:defaultdict(lambda:{"inflow":ZERO,"outflow":ZERO}) for key in ("OPERATING","INVESTING","FINANCING","UNCLASSIFIED")}
    for m in svc.movements(date_from,date_to,account_id,location_id=location_id):
        if m["direction"]=="TRANSFER":continue
        key=m["category"] if m["category"] in sections else "UNCLASSIFIED";label=m["journal"].reference_type or "OTHER";sections[key][label]["inflow"]+=m["inflow"];sections[key][label]["outflow"]+=m["outflow"]
    result={}
    for category,groups in sections.items():result[category.lower()]={"items":[{"transaction_group":label,**values,"net":values["inflow"]-values["outflow"]} for label,values in groups.items()],"net":sum((v["inflow"]-v["outflow"] for v in groups.values()),ZERO)}
    result.update({"net_operating_cash_flow":summary_data["operating_net"],"net_investing_cash_flow":summary_data["investing_net"],"net_financing_cash_flow":summary_data["financing_net"],"net_change_in_cash":summary_data["net_cash_flow"],"opening_cash":summary_data["opening_cash_balance"],"closing_cash":summary_data["closing_cash_balance"],"unclassified_transactions":summary_data["unclassified_count"]});return result

@router.get("/movements/{journal_line_id}/trace")
def trace(journal_line_id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user)
    svc=CashFlowService(db)
    traced=svc.trace(journal_line_id)
    line=svc.db.get(__import__("app.models.journal_line",fromlist=["JournalLine"]).JournalLine,journal_line_id)
    require_location_access(line.location_id if line else None,user)
    return traced
