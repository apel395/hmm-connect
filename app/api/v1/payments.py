from datetime import date,datetime,timezone
from decimal import Decimal
from math import ceil
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.accounting_posting_rule import AccountingPostingRule
from app.models.chart_of_account import ChartOfAccount
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.payment import Payment,PaymentAllocation
from app.models.supplier_invoice import SupplierInvoice
from app.schemas.payment import PaymentCreate,PaymentUpdate
from app.services.audit import record_audit
from app.services.document_context import document_context,print_metadata
from app.services.document_number import next_document_number
from app.services.general_ledger import GeneralLedgerService
router=APIRouter(prefix="/payments",tags=["Payments"]);ZERO=Decimal("0")
def access(user):
    if not {r.name for r in user.roles}.intersection({"FINANCE","ADMIN"}):raise HTTPException(403,"Finance access required")
def get(db,id):
    x=db.get(Payment,id)
    if not x:raise HTTPException(404,"Payment not found")
    return x
def validate_account(db,id):
    a=db.get(ChartOfAccount,id)
    if not a or not a.is_active or not a.is_posting or a.account_type!="ASSET" or a.account_subtype not in {"CASH","BANK","PETTY_CASH"}:raise HTTPException(400,"Payment account must be an active posting cash, bank, or petty-cash account")
    return a
def validate_data(db,data,exclude=None):
    validate_account(db,data.payment_account_id);total=ZERO
    for allocation in data.allocations:
        invoice=db.get(SupplierInvoice,allocation.supplier_invoice_id)
        if not invoice or invoice.supplier_id!=data.supplier_id:raise HTTPException(400,"Allocated invoice does not belong to selected supplier")
        if invoice.status!="POSTED" or invoice.payment_status=="PAID":raise HTTPException(409,"Only posted unpaid invoices can be allocated")
        if invoice.currency!=data.currency:raise HTTPException(400,"Payment and invoice currencies must match")
        reserved=db.query(PaymentAllocation).join(Payment).filter(PaymentAllocation.supplier_invoice_id==invoice.id,Payment.status=="APPROVED")
        if exclude:reserved=reserved.filter(Payment.id!=exclude)
        available=Decimal(invoice.balance_amount)-sum((Decimal(x.allocated_amount) for x in reserved.all()),ZERO)
        if allocation.allocated_amount>available:raise HTTPException(409,f"Allocation exceeds outstanding balance for {invoice.internal_invoice_number}")
        total+=allocation.allocated_amount
    if total!=data.total_amount:raise HTTPException(400,"Total allocations must equal payment total")
def serialize(x):
    allocated=sum((Decimal(a.allocated_amount) for a in x.allocations),ZERO)
    return {"id":x.id,"payment_number":x.payment_number,"supplier_id":x.supplier_id,"supplier_name":x.supplier.name if x.supplier else None,"payment_date":x.payment_date,"payment_method":x.payment_method,"payment_account_id":x.payment_account_id,"payment_account_code":x.payment_account.account_number if x.payment_account else None,"payment_account_name":x.payment_account.account_name if x.payment_account else None,"currency":x.currency,"total_amount":x.amount,"allocated_amount":allocated,"reference_number":x.reference_number,"cheque_number":x.cheque_number,"status":x.status,"notes":x.notes,"source_type":x.source_type,"journal_entry_id":x.journal_entry_id,"journal_number":x.journal_entry.journal_number if x.journal_entry else None,"created_by_name":x.created_by.full_name if x.created_by else None,"approved_by_name":x.approved_by.full_name if x.approved_by else None,"posted_by_name":x.posted_by.full_name if x.posted_by else None,"created_at":x.created_at,"updated_at":x.updated_at,"approved_at":x.approved_at,"posted_at":x.posted_at,"voided_at":x.voided_at,"allocations":[{"id":a.id,"supplier_invoice_id":a.supplier_invoice_id,"invoice_number":a.supplier_invoice.internal_invoice_number,"invoice_date":a.supplier_invoice.invoice_date,"due_date":a.supplier_invoice.due_date,"invoice_total":a.supplier_invoice.total_amount,"paid_amount":a.supplier_invoice.paid_amount,"outstanding_balance":a.supplier_invoice.balance_amount,"allocated_amount":a.allocated_amount} for a in x.allocations]}
def result(db,x,user):
    data=serialize(x);data.update(document_context(db,"PAYMENT",x.id,x.status,user));data["allowed_actions"]={"can_edit":x.status=="DRAFT","can_approve":x.status=="DRAFT","can_generate_journal":x.status=="APPROVED" and not x.journal_entry_id,"can_post":x.status=="APPROVED" and bool(x.journal_entry_id and x.journal_entry.status=="DRAFT"),"can_void":x.status in {"DRAFT","APPROVED"},"can_print":True,"can_manage_attachments":True,"can_view_history":True};return data
@router.get("")
def listing(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),search:str|None=None,supplier_id:int|None=None,status:str|None=None,payment_method:str|None=None,payment_date_from:date|None=None,payment_date_to:date|None=None,source_type:str|None=None,db:Session=Depends(get_db),_=Depends(get_current_user)):
    access(_)
    q=db.query(Payment)
    if search:q=q.filter(or_(Payment.payment_number.ilike(f"%{search}%"),Payment.reference_number.ilike(f"%{search}%")))
    if supplier_id:q=q.filter(Payment.supplier_id==supplier_id)
    if status:q=q.filter(Payment.status==status)
    if payment_method:q=q.filter(Payment.payment_method==payment_method)
    if payment_date_from:q=q.filter(Payment.payment_date>=payment_date_from)
    if payment_date_to:q=q.filter(Payment.payment_date<=payment_date_to)
    if source_type:q=q.filter(Payment.source_type==source_type)
    total=q.count();rows=q.order_by(Payment.id.desc()).offset((page-1)*page_size).limit(page_size).all();return {"items":[serialize(x) for x in rows],"page":page,"page_size":page_size,"total_items":total,"total_pages":ceil(total/page_size) if total else 0,"has_next":page*page_size<total,"has_previous":page>1}
@router.get("/eligible-invoices")
def eligible(supplier_id:int,currency:str="IDR",db:Session=Depends(get_db),_=Depends(get_current_user)):
    access(_)
    rows=db.query(SupplierInvoice).filter(SupplierInvoice.supplier_id==supplier_id,SupplierInvoice.currency==currency,SupplierInvoice.status=="POSTED",SupplierInvoice.balance_amount>0).order_by(SupplierInvoice.due_date,SupplierInvoice.id).all();return [{"id":x.id,"invoice_number":x.internal_invoice_number,"supplier_invoice_number":x.supplier_invoice_number,"invoice_date":x.invoice_date,"due_date":x.due_date,"total_amount":x.total_amount,"paid_amount":x.paid_amount,"outstanding_balance":x.balance_amount,"currency":x.currency} for x in rows]
@router.get("/{payment_id}")
def detail(payment_id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):access(user);return result(db,get(db,payment_id),user)
@router.post("",status_code=201)
def create(data:PaymentCreate,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);validate_data(db,data);x=Payment(payment_number=next_document_number(db,"PAY"),supplier_id=data.supplier_id,payment_date=data.payment_date,amount=data.total_amount,payment_method=data.payment_method,payment_account_id=data.payment_account_id,currency=data.currency,reference_number=data.reference_number,cheque_number=data.cheque_number,notes=data.notes,source_type=data.source_type,status="DRAFT",created_by_id=user.id)
    for a in data.allocations:x.allocations.append(PaymentAllocation(**a.model_dump()))
    db.add(x);db.flush();record_audit(db,user,"PAYMENT_CREATED","PAYMENT",f"Created {x.payment_number}",entity_id=x.id)
    for a in x.allocations:record_audit(db,user,"PAYMENT_ALLOCATION_ADDED","PAYMENT",f"Allocated {a.allocated_amount} to invoice {a.supplier_invoice_id}",entity_id=x.id)
    db.commit();db.refresh(x);return result(db,x,user)
@router.patch("/{payment_id}")
def update(payment_id:int,data:PaymentUpdate,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);x=get(db,payment_id)
    if x.status!="DRAFT":raise HTTPException(409,"Only draft payments can be edited")
    validate_data(db,data,x.id)
    for k,v in data.model_dump(exclude={"allocations","total_amount"}).items():setattr(x,k,v)
    for a in x.allocations:record_audit(db,user,"PAYMENT_ALLOCATION_REMOVED","PAYMENT",f"Removed allocation {a.allocated_amount} from invoice {a.supplier_invoice_id}",entity_id=x.id)
    x.amount=data.total_amount;x.allocations.clear()
    for a in data.allocations:x.allocations.append(PaymentAllocation(**a.model_dump()))
    db.flush()
    for a in x.allocations:record_audit(db,user,"PAYMENT_ALLOCATION_ADDED","PAYMENT",f"Allocated {a.allocated_amount} to invoice {a.supplier_invoice_id}",entity_id=x.id)
    record_audit(db,user,"PAYMENT_UPDATED","PAYMENT",f"Updated {x.payment_number}",entity_id=x.id);db.commit();db.refresh(x);return result(db,x,user)
@router.post("/{payment_id}/approve")
def approve(payment_id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);x=get(db,payment_id)
    if x.status!="DRAFT":raise HTTPException(409,"Only draft payments can be approved")
    if sum((Decimal(a.allocated_amount) for a in x.allocations),ZERO)!=Decimal(x.amount):raise HTTPException(409,"Allocations must equal payment total")
    for a in x.allocations:
        invoice=db.query(SupplierInvoice).filter(SupplierInvoice.id==a.supplier_invoice_id).with_for_update().one()
        reserved=db.query(PaymentAllocation).join(Payment).filter(PaymentAllocation.supplier_invoice_id==invoice.id,Payment.status=="APPROVED",Payment.id!=x.id)
        available=Decimal(invoice.balance_amount)-sum((Decimal(row.allocated_amount) for row in reserved.all()),ZERO)
        if Decimal(a.allocated_amount)>available:raise HTTPException(409,f"Allocation exceeds outstanding balance for {invoice.internal_invoice_number}")
    x.status="APPROVED";x.approved_by_id=user.id;x.approved_at=datetime.now(timezone.utc);record_audit(db,user,"PAYMENT_APPROVED","PAYMENT",f"Approved {x.payment_number}",entity_id=x.id);db.commit();db.refresh(x);return result(db,x,user)
@router.post("/{payment_id}/generate-journal")
def generate(payment_id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);x=get(db,payment_id)
    if x.status!="APPROVED":raise HTTPException(409,"Payment must be approved")
    if x.journal_entry_id:raise HTTPException(409,"Payment already has a journal")
    rule=db.query(AccountingPostingRule).filter_by(event_type="SUPPLIER_PAYMENT",is_active=True).first()
    if not rule:raise HTTPException(409,"No active SUPPLIER_PAYMENT posting rule configured")
    bank=validate_account(db,x.payment_account_id)
    if rule.debit_account_id==bank.id:raise HTTPException(409,"Payable and payment accounts must differ")
    journal=JournalEntry(journal_number=next_document_number(db,"JV"),posting_date=x.payment_date,status="DRAFT",document_type="SUPPLIER_PAYMENT",document_number=x.payment_number,reference_type="SUPPLIER_PAYMENT",reference_id=x.id,description=f"Supplier payment {x.payment_number}",created_by_id=user.id,posted_at=None)
    category=rule.debit_account.cash_flow_category if rule.debit_account.cash_flow_category in {"OPERATING","INVESTING","FINANCING"} else "OPERATING"
    journal.lines=[JournalLine(line_number=1,account_id=rule.debit_account_id,debit=x.amount,credit=0,description="Accounts Payable",supplier_id=x.supplier_id,cash_flow_category=category,cash_flow_direction="OUTFLOW"),JournalLine(line_number=2,account_id=bank.id,debit=0,credit=x.amount,description="Cash / Bank",supplier_id=x.supplier_id,cash_flow_category=category,cash_flow_direction="OUTFLOW")]
    db.add(journal);db.flush();x.journal_entry_id=journal.id;record_audit(db,user,"PAYMENT_JOURNAL_GENERATED","PAYMENT",f"Generated {journal.journal_number} for {x.payment_number}",entity_id=x.id);db.commit();db.refresh(x);return result(db,x,user)
@router.post("/{payment_id}/post")
def post(payment_id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);x=db.query(Payment).filter(Payment.id==payment_id).with_for_update().first()
    if not x or x.status!="APPROVED" or not x.journal_entry_id:raise HTTPException(409,"Approved payment with draft journal required")
    journal=db.query(JournalEntry).filter(JournalEntry.id==x.journal_entry_id).with_for_update().one()
    if journal.status!="DRAFT":raise HTTPException(409,"Payment journal is not draft")
    debit=sum((Decimal(l.debit) for l in journal.lines),ZERO);credit=sum((Decimal(l.credit) for l in journal.lines),ZERO)
    if debit!=credit or debit!=Decimal(x.amount):raise HTTPException(409,"Payment journal is not balanced")
    for a in x.allocations:
        invoice=db.query(SupplierInvoice).filter(SupplierInvoice.id==a.supplier_invoice_id).with_for_update().one();amount=Decimal(a.allocated_amount)
        if amount>Decimal(invoice.balance_amount):raise HTTPException(409,"Allocation exceeds invoice outstanding balance")
        invoice.paid_amount=Decimal(invoice.paid_amount)+amount;invoice.balance_amount=Decimal(invoice.total_amount)-Decimal(invoice.paid_amount);invoice.payment_status="PAID" if invoice.balance_amount==0 else "PARTIALLY_PAID"
    for l in journal.lines:GeneralLedgerService.post(db=db,account_id=l.account_id,debit=l.debit,credit=l.credit,posting_date=journal.posting_date,journal_source="SUPPLIER_PAYMENT",document_type=journal.document_type,document_number=journal.document_number,reference_type=journal.reference_type,reference_id=journal.reference_id,reference_number=journal.journal_number,description=l.description,user_id=user.id)
    now=datetime.now(timezone.utc);journal.status="POSTED";journal.posted_by_id=user.id;journal.posted_at=now;x.status="POSTED";x.posted_by_id=user.id;x.posted_at=now;record_audit(db,user,"PAYMENT_POSTED","PAYMENT",f"Posted {x.payment_number}",entity_id=x.id,reference_document=journal.journal_number);db.commit();db.refresh(x);return result(db,x,user)
@router.post("/{payment_id}/void")
def void(payment_id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);x=get(db,payment_id)
    if x.status=="POSTED":raise HTTPException(409,"Posted payments require a reversal and cannot be voided")
    if x.status=="VOID":raise HTTPException(409,"Payment is already void")
    x.status="VOID";x.voided_at=datetime.now(timezone.utc)
    if x.journal_entry and x.journal_entry.status=="DRAFT":x.journal_entry.status="VOID";x.journal_entry.voided_at=x.voided_at
    record_audit(db,user,"PAYMENT_VOIDED","PAYMENT",f"Voided {x.payment_number}",entity_id=x.id);db.commit();db.refresh(x);return result(db,x,user)
@router.get("/{payment_id}/allowed-actions")
def actions(payment_id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):access(user);return result(db,get(db,payment_id),user)["allowed_actions"]
@router.get("/{payment_id}/print")
def printable(payment_id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):access(user);return {**result(db,get(db,payment_id),user),"document_type":"Supplier Payment",**print_metadata(user)}
