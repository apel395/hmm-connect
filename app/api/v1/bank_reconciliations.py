import json
from datetime import date, datetime, timezone
from decimal import Decimal
from math import ceil
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_permission
from app.models.bank_reconciliation import BankReconciliation, BankStatementLine, BankReconciliationMatch
from app.models.chart_of_account import ChartOfAccount
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.schemas.bank_reconciliation import ReconciliationCreate,ReconciliationUpdate,MatchCreate,AutoMatchRequest,AdjustmentCreate
from app.services.audit import record_audit
from app.services.bank_reconciliation_service import BankReconciliationService, ZERO
from app.services.document_number import next_document_number

router=APIRouter(prefix="/bank-reconciliations",tags=["Bank Reconciliation"])
def access(user):
    if not has_permission(user, "finance.manage"):raise HTTPException(403,"Finance access required")
def fail(e):raise HTTPException(400,str(e))
def audit(db,user,action,r,text):record_audit(db,user,action,"BANK_RECONCILIATION",text,entity_id=r.id,reference_document=r.reconciliation_number)

@router.get("/accounts")
def accounts(db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);return [{"id":x.id,"account_code":x.account_number,"account_name":x.account_name,"account_subtype":x.account_subtype} for x in db.query(ChartOfAccount).filter(ChartOfAccount.is_active.is_(True),ChartOfAccount.is_posting.is_(True),ChartOfAccount.account_type=="ASSET",ChartOfAccount.account_subtype=="BANK").order_by(ChartOfAccount.account_number)]
@router.get("")
def listing(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),account_id:int|None=None,status:str|None=None,date_from:date|None=None,date_to:date|None=None,created_by_id:int|None=None,search:str|None=None,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);q=db.query(BankReconciliation)
    if account_id:q=q.filter(BankReconciliation.account_id==account_id)
    if status:q=q.filter(BankReconciliation.status==status)
    if date_from:q=q.filter(BankReconciliation.statement_end_date>=date_from)
    if date_to:q=q.filter(BankReconciliation.statement_start_date<=date_to)
    if created_by_id:q=q.filter(BankReconciliation.created_by_id==created_by_id)
    if search:q=q.join(BankReconciliation.account).filter(or_(BankReconciliation.reconciliation_number.ilike(f"%{search}%"),ChartOfAccount.account_name.ilike(f"%{search}%")))
    total=q.count();svc=BankReconciliationService(db);items=[svc.serialize(x) for x in q.order_by(BankReconciliation.statement_end_date.desc(),BankReconciliation.id.desc()).offset((page-1)*page_size).limit(page_size)]
    return {"items":items,"page":page,"page_size":page_size,"total_items":total,"total_pages":ceil(total/page_size) if total else 0}
@router.post("")
def create(data:ReconciliationCreate,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);svc=BankReconciliationService(db)
    try:r=svc.create(data,user)
    except ValueError as e:fail(e)
    audit(db,user,"BANK_RECONCILIATION_CREATED",r,f"Created {r.reconciliation_number}");db.commit();db.refresh(r);return svc.serialize(r,True)
@router.get("/{id}")
def detail(id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);svc=BankReconciliationService(db)
    try:return svc.serialize(svc.get(id),True)
    except ValueError as e:fail(e)
@router.patch("/{id}")
def update(id:int,data:ReconciliationUpdate,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);svc=BankReconciliationService(db)
    try:r=svc.get(id,True)
    except ValueError as e:fail(e)
    if r.status not in ("DRAFT","IN_PROGRESS"):raise HTTPException(409,"Completed reconciliation is locked")
    for k,v in data.model_dump(exclude_unset=True).items():setattr(r,k,v)
    if r.statement_start_date>r.statement_end_date:raise HTTPException(400,"Statement period is invalid")
    svc.recalc(r);db.commit();db.refresh(r);return svc.serialize(r)
@router.post("/{id}/upload-statement")
async def upload(id:int,file:UploadFile=File(),mapping_json:str=Form("{}"),preview:bool=Form(False),db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);svc=BankReconciliationService(db)
    try:r=svc.get(id,True)
    except ValueError as e:fail(e)
    if r.status not in ("DRAFT","IN_PROGRESS"):raise HTTPException(409,"Completed reconciliation is locked")
    try:parsed,errors,total=svc.parse(await file.read(),file.filename or "statement.csv",json.loads(mapping_json))
    except (ValueError,json.JSONDecodeError) as e:fail(e)
    existing={(x.external_transaction_id,x.transaction_date,max(Decimal(x.debit),Decimal(x.credit))) for x in r.statement_lines};accepted=[];duplicates=0
    for row in parsed:
        key=(row["external_transaction_id"],row["transaction_date"],max(row["debit"],row["credit"]))
        if key in existing and key[0]:duplicates+=1;continue
        accepted.append(row);existing.add(key)
    if preview:return {"rows_detected":total,"rows_accepted":len(accepted),"duplicates":duplicates,"errors":errors,"preview":accepted[:25]}
    for row in accepted:r.statement_lines.append(BankStatementLine(**row))
    r.source_filename=file.filename;r.status="IN_PROGRESS";svc.recalc(r);audit(db,user,"BANK_STATEMENT_IMPORTED",r,f"Imported {len(accepted)} statement rows");db.commit();return {"rows_detected":total,"rows_accepted":len(accepted),"duplicates":duplicates,"errors":errors}
@router.get("/{id}/statement-lines")
def statement_lines(id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);svc=BankReconciliationService(db)
    try:r=svc.get(id)
    except ValueError as e:fail(e)
    return [{"id":x.id,"transaction_date":x.transaction_date,"value_date":x.value_date,"description":x.description,"reference_number":x.reference_number,"debit":x.debit,"credit":x.credit,"balance":x.balance,"external_transaction_id":x.external_transaction_id,"counterparty_name":x.counterparty_name,"match_status":x.match_status,"matched_amount":sum((Decimal(m.matched_amount) for m in x.matches),ZERO),"matches":[{"id":m.id,"journal_line_id":m.journal_line_id,"matched_amount":m.matched_amount,"match_type":m.match_type,"confidence_score":m.confidence_score} for m in x.matches]} for x in r.statement_lines]
@router.get("/{id}/system-transactions")
def system_transactions(id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);svc=BankReconciliationService(db)
    try:return svc.system_rows(svc.get(id))
    except ValueError as e:fail(e)
@router.post("/{id}/auto-match")
def auto_match(id:int,data:AutoMatchRequest,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);svc=BankReconciliationService(db)
    try:r=svc.get(id,True);created,suggestions=svc.auto_match(r,user,data.date_tolerance_days,data.confirm_suggested);svc.recalc(r)
    except ValueError as e:fail(e)
    audit(db,user,"BANK_RECONCILIATION_AUTO_MATCHED",r,f"Created {len(created)} exact matches");db.commit();return {"created_match_ids":created,"suggestions":suggestions}
@router.post("/{id}/matches")
def match(id:int,data:MatchCreate,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);svc=BankReconciliationService(db)
    try:r=svc.get(id,True);created=[svc.add_match(r,x,user).id for x in data.allocations];svc.recalc(r)
    except ValueError as e:fail(e)
    audit(db,user,"BANK_RECONCILIATION_MATCH_CREATED",r,f"Created {len(created)} match allocations");db.commit();return {"match_ids":created,"summary":svc.serialize(r)}
@router.delete("/{id}/matches/{match_id}")
def unmatch(id:int,match_id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);svc=BankReconciliationService(db)
    try:r=svc.get(id,True)
    except ValueError as e:fail(e)
    if r.status not in ("DRAFT","IN_PROGRESS"):raise HTTPException(409,"Completed reconciliation is locked")
    m=db.get(BankReconciliationMatch,match_id)
    if not m or m.reconciliation_id!=id:raise HTTPException(404,"Match not found")
    line=m.statement_line;db.delete(m);db.flush();remaining=sum((Decimal(x.matched_amount) for x in line.matches),ZERO);line.match_status="UNMATCHED" if remaining==ZERO else "PARTIAL";line.matched_journal_line_id=None;line.matched_at=None if remaining==ZERO else line.matched_at;svc.recalc(r);audit(db,user,"BANK_RECONCILIATION_MATCH_REMOVED",r,"Removed match allocation");db.commit();return svc.serialize(r)
@router.post("/{id}/create-adjustment")
def adjustment(id:int,data:AdjustmentCreate,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);svc=BankReconciliationService(db)
    try:r=svc.get(id,True)
    except ValueError as e:fail(e)
    if r.status not in ("DRAFT","IN_PROGRESS"):raise HTTPException(409,"Completed reconciliation is locked")
    if data.adjustment_type not in {"BANK_FEE","BANK_INTEREST","TAX_WITHHOLDING","OTHER_BANK_ADJUSTMENT"}:raise HTTPException(400,"Invalid adjustment type")
    line=db.get(BankStatementLine,data.statement_line_id)
    if not line or line.reconciliation_id!=id or line.match_status!="UNMATCHED":raise HTTPException(400,"Select an unmatched statement line")
    debit=db.get(ChartOfAccount,data.debit_account_id);credit=db.get(ChartOfAccount,data.credit_account_id)
    if not debit or not credit or not debit.is_posting or not credit.is_posting or r.account_id not in (debit.id,credit.id):raise HTTPException(400,"Adjustment must use posting accounts and the selected bank account")
    journal=JournalEntry(journal_number=next_document_number(db,"JE"),posting_date=data.posting_date,status="DRAFT",document_type="BANK_RECONCILIATION",document_number=r.reconciliation_number,reference_type=data.adjustment_type,reference_id=r.id,description=data.description,created_by_id=user.id,posted_at=None,lines=[JournalLine(account_id=debit.id,debit=data.amount,credit=ZERO,description=data.notes or data.description,line_number=1),JournalLine(account_id=credit.id,debit=ZERO,credit=data.amount,description=data.notes or data.description,line_number=2)])
    db.add(journal);db.flush();audit(db,user,"BANK_RECONCILIATION_ADJUSTMENT_CREATED",r,f"Created draft adjustment {journal.journal_number}");db.commit();return {"journal_id":journal.id,"journal_number":journal.journal_number,"route":f"/journal-entries/{journal.id}"}
@router.post("/{id}/complete")
def complete(id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);svc=BankReconciliationService(db)
    try:r=svc.get(id,True);svc.recalc(r)
    except ValueError as e:fail(e)
    if r.status not in ("DRAFT","IN_PROGRESS"):raise HTTPException(409,"Reconciliation cannot be completed")
    if r.difference!=ZERO:raise HTTPException(409,f"Difference must be zero; current difference is {r.difference}")
    partial=sum(x.match_status=="PARTIAL" for x in r.statement_lines)
    if partial:raise HTTPException(409,"Partial statement matches must be fully reconciled")
    draft_adjustments=db.query(JournalEntry).filter(JournalEntry.reference_id==r.id,JournalEntry.reference_type.in_(["BANK_FEE","BANK_INTEREST","TAX_WITHHOLDING","OTHER_BANK_ADJUSTMENT"]),JournalEntry.status!="POSTED").count()
    if draft_adjustments:raise HTTPException(409,"All reconciliation adjustment journals must be posted")
    now=datetime.now(timezone.utc);r.status="COMPLETED";r.completed_by_id=user.id;r.completed_at=now;audit(db,user,"BANK_RECONCILIATION_COMPLETED",r,f"Completed {r.reconciliation_number}");db.commit();db.refresh(r);return svc.serialize(r)
@router.post("/{id}/void")
def void(id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);svc=BankReconciliationService(db)
    try:r=svc.get(id,True)
    except ValueError as e:fail(e)
    if r.status=="COMPLETED":raise HTTPException(409,"Completed reconciliation requires a controlled reversal")
    if r.status=="VOID":raise HTTPException(409,"Reconciliation is already void")
    r.status="VOID";r.voided_at=datetime.now(timezone.utc);audit(db,user,"BANK_RECONCILIATION_VOIDED",r,f"Voided {r.reconciliation_number}");db.commit();return svc.serialize(r)
@router.get("/{id}/summary")
def summary(id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):return detail(id,db,user)
@router.get("/{id}/print")
def printable(id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):
    data=detail(id,db,user);data["statement_lines"]=statement_lines(id,db,user);data["system_transactions"]=system_transactions(id,db,user);data["printed_at"]=datetime.now(timezone.utc);data["document_type"]="Bank Reconciliation";return data