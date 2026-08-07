from datetime import datetime,timezone
from decimal import Decimal
from math import ceil
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_any_role
from app.models.bank_transfer import BankTransfer
from app.models.chart_of_account import ChartOfAccount
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.schemas.bank_transfer import BankTransferInput
from app.services.audit import record_audit
from app.services.document_context import print_metadata
from app.services.document_number import next_document_number
from app.services.general_ledger import GeneralLedgerService

router=APIRouter(prefix="/bank-transfers",tags=["Bank Transfers"]);CASH_TYPES={"CASH","BANK","PETTY_CASH"}
def access(user):
    if not has_any_role(user,"FINANCE"):raise HTTPException(403,"Finance access required")
def get(db,id):
    x=db.get(BankTransfer,id)
    if not x:raise HTTPException(404,"Bank transfer not found")
    return x
def account(db,id):
    x=db.get(ChartOfAccount,id)
    if not x or x.account_type!="ASSET" or x.account_subtype not in CASH_TYPES or not x.is_active or not x.is_posting:raise HTTPException(400,"Transfer accounts must be active cash/bank posting accounts")
    return x
def validate(db,data):
    source=account(db,data.source_account_id);destination=account(db,data.destination_account_id)
    if source.id==destination.id:raise HTTPException(400,"Source and destination accounts must differ")
    return source,destination
def serialize(x):return {"id":x.id,"transfer_number":x.transfer_number,"transfer_date":x.transfer_date,"source_account_id":x.source_account_id,"source_account_code":x.source_account.account_number,"source_account_name":x.source_account.account_name,"destination_account_id":x.destination_account_id,"destination_account_code":x.destination_account.account_number,"destination_account_name":x.destination_account.account_name,"amount":x.amount,"currency":x.currency,"reference_number":x.reference_number,"notes":x.notes,"status":x.status,"journal_entry_id":x.journal_entry_id,"journal_number":x.journal_entry.journal_number if x.journal_entry else None,"created_by_name":x.created_by.full_name if x.created_by else None,"posted_by_name":x.posted_by.full_name if x.posted_by else None,"created_at":x.created_at,"updated_at":x.updated_at,"posted_at":x.posted_at,"allowed_actions":{"can_edit":x.status=="DRAFT","can_post":x.status=="DRAFT","can_print":True}}
@router.get("")
def listing(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),status:str|None=None,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);q=db.query(BankTransfer)
    if status:q=q.filter(BankTransfer.status==status)
    total=q.count();items=q.order_by(BankTransfer.transfer_date.desc(),BankTransfer.id.desc()).offset((page-1)*page_size).limit(page_size).all();return {"items":[serialize(x) for x in items],"page":page,"page_size":page_size,"total_items":total,"total_pages":ceil(total/page_size) if total else 0,"has_next":page*page_size<total,"has_previous":page>1}
@router.get("/{transfer_id}")
def detail(transfer_id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):access(user);return serialize(get(db,transfer_id))
@router.post("",status_code=201)
def create(data:BankTransferInput,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);validate(db,data);x=BankTransfer(transfer_number=next_document_number(db,"BT"),status="DRAFT",created_by_id=user.id,**data.model_dump());db.add(x);db.flush();record_audit(db,user,"BANK_TRANSFER_CREATED","BANK_TRANSFER",f"Created {x.transfer_number}",entity_id=x.id);db.commit();db.refresh(x);return serialize(x)
@router.patch("/{transfer_id}")
def update(transfer_id:int,data:BankTransferInput,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);x=get(db,transfer_id)
    if x.status!="DRAFT":raise HTTPException(409,"Only draft transfers can be edited")
    validate(db,data)
    for key,value in data.model_dump().items():setattr(x,key,value)
    record_audit(db,user,"BANK_TRANSFER_UPDATED","BANK_TRANSFER",f"Updated {x.transfer_number}",entity_id=x.id);db.commit();db.refresh(x);return serialize(x)
@router.post("/{transfer_id}/post")
def post(transfer_id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);x=db.query(BankTransfer).filter(BankTransfer.id==transfer_id).with_for_update().first()
    if not x or x.status!="DRAFT":raise HTTPException(409,"Only draft transfers can be posted")
    source,destination=validate(db,BankTransferInput(transfer_date=x.transfer_date,source_account_id=x.source_account_id,destination_account_id=x.destination_account_id,amount=x.amount,currency=x.currency,reference_number=x.reference_number,notes=x.notes))
    journal=JournalEntry(journal_number=next_document_number(db,"JV"),posting_date=x.transfer_date,status="DRAFT",document_type="BANK_TRANSFER",document_number=x.transfer_number,reference_type="BANK_TRANSFER",reference_id=x.id,description=f"Internal transfer {x.transfer_number}",created_by_id=user.id,posted_at=None)
    journal.lines=[JournalLine(line_number=1,account_id=destination.id,debit=x.amount,credit=0,description=f"Transfer from {source.account_number}",cash_flow_category="NON_CASH",cash_flow_direction="TRANSFER"),JournalLine(line_number=2,account_id=source.id,debit=0,credit=x.amount,description=f"Transfer to {destination.account_number}",cash_flow_category="NON_CASH",cash_flow_direction="TRANSFER")]
    db.add(journal);db.flush()
    for line in journal.lines:GeneralLedgerService.post(db=db,account_id=line.account_id,debit=line.debit,credit=line.credit,posting_date=journal.posting_date,journal_source="BANK_TRANSFER",document_type=journal.document_type,document_number=journal.document_number,reference_type=journal.reference_type,reference_id=journal.reference_id,reference_number=journal.journal_number,description=line.description,user_id=user.id)
    now=datetime.now(timezone.utc);journal.status="POSTED";journal.posted_by_id=user.id;journal.posted_at=now;x.status="POSTED";x.posted_by_id=user.id;x.posted_at=now;x.journal_entry_id=journal.id;record_audit(db,user,"BANK_TRANSFER_POSTED","BANK_TRANSFER",f"Posted {x.transfer_number}",entity_id=x.id,reference_document=journal.journal_number);db.commit();db.refresh(x);return serialize(x)
@router.get("/{transfer_id}/allowed-actions")
def actions(transfer_id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):access(user);return serialize(get(db,transfer_id))["allowed_actions"]
@router.get("/{transfer_id}/print")
def printable(transfer_id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):access(user);return {**serialize(get(db,transfer_id)),"document_type":"Bank Transfer",**print_metadata(user)}
