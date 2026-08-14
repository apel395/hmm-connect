from datetime import date
from decimal import Decimal
from math import ceil
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy import func,or_
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_any_role
from app.models.chart_of_account import ChartOfAccount
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
router=APIRouter(prefix="/general-ledger",tags=["General Ledger"]);ZERO=Decimal("0")
def access(user):
    if not has_any_role(user,"FINANCE"):raise HTTPException(403,"Finance access required")
def base(db,account_id=None,date_from=None,date_to=None,reference_type=None,supplier_id=None,department_id=None,location_id=None,search=None,business_unit_id=None):
    q=db.query(JournalLine).join(JournalEntry).filter(JournalEntry.status=="POSTED")
    if account_id:q=q.filter(JournalLine.account_id==account_id)
    if date_from:q=q.filter(JournalEntry.posting_date>=date_from)
    if date_to:q=q.filter(JournalEntry.posting_date<=date_to)
    if reference_type:q=q.filter(JournalEntry.reference_type==reference_type)
    if supplier_id:q=q.filter(JournalLine.supplier_id==supplier_id)
    if department_id:q=q.filter(JournalLine.department_id==department_id)
    if location_id:q=q.filter(JournalLine.location_id==location_id)
    if business_unit_id:q=q.filter(JournalLine.business_unit_id==business_unit_id)
    if search:q=q.filter(or_(JournalEntry.journal_number.ilike(f"%{search}%"),JournalEntry.document_number.ilike(f"%{search}%"),JournalLine.description.ilike(f"%{search}%")))
    return q
@router.get("")
def listing(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),search:str|None=None,account_id:int|None=None,date_from:date|None=None,date_to:date|None=None,reference_type:str|None=None,supplier_id:int|None=None,department_id:int|None=None,location_id:int|None=None,business_unit_id:int|None=None,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);q=base(db,account_id,date_from,date_to,reference_type,supplier_id,department_id,location_id,search,business_unit_id);total=q.count();all_rows=q.order_by(JournalEntry.posting_date,JournalEntry.id,JournalLine.line_number,JournalLine.id).all();balances={};serialized=[]
    for line in all_rows:
        a=line.account;delta=Decimal(line.debit)-Decimal(line.credit) if a.normal_balance=="DEBIT" else Decimal(line.credit)-Decimal(line.debit);balances[a.id]=balances.get(a.id,ZERO)+delta;serialized.append({"id":line.id,"posting_date":line.journal_entry.posting_date,"journal_id":line.journal_entry.id,"journal_number":line.journal_entry.journal_number,"account_id":a.id,"account_code":a.account_number,"account_name":a.account_name,"description":line.description,"reference_type":line.journal_entry.reference_type,"reference_number":line.journal_entry.document_number,"debit":line.debit,"credit":line.credit,"balance":balances[a.id],"supplier_id":line.supplier_id,"supplier_name":line.supplier.name if line.supplier else None,"department_id":line.department_id,"department_name":line.department.name if line.department else None,"location_id":line.location_id,"location_name":line.location.name if line.location else None})
    items=serialized[(page-1)*page_size:page*page_size];return {"items":items,"page":page,"page_size":page_size,"total_items":total,"total_pages":ceil(total/page_size) if total else 0,"has_next":page*page_size<total,"has_previous":page>1}
@router.get("/accounts/{account_id}/summary")
def summary(account_id:int,date_from:date|None=None,date_to:date|None=None,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);account=db.get(ChartOfAccount,account_id)
    if not account:raise HTTPException(404,"Account not found")
    opening_q=base(db,account_id,date_to=(date_from if date_from else None))
    if date_from:opening_q=opening_q.filter(JournalEntry.posting_date<date_from)
    else:opening_q=opening_q.filter(False)
    od,oc=opening_q.with_entities(func.coalesce(func.sum(JournalLine.debit),0),func.coalesce(func.sum(JournalLine.credit),0)).one();q=base(db,account_id,date_from,date_to);td,tc=q.with_entities(func.coalesce(func.sum(JournalLine.debit),0),func.coalesce(func.sum(JournalLine.credit),0)).one();opening=Decimal(od)-Decimal(oc) if account.normal_balance=="DEBIT" else Decimal(oc)-Decimal(od);movement=Decimal(td)-Decimal(tc) if account.normal_balance=="DEBIT" else Decimal(tc)-Decimal(td);return {"account_id":account.id,"account_code":account.account_number,"account_name":account.account_name,"normal_balance":account.normal_balance,"opening_balance":opening,"total_debit":td,"total_credit":tc,"closing_balance":opening+movement}
