from datetime import date, datetime, timezone
from math import ceil
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.journal_entry import JournalEntry
from app.models.supplier_invoice import SupplierInvoice
from app.schemas.supplier_invoice import SupplierInvoiceInput
from app.services.audit import record_audit
from app.services.document_context import document_context,print_metadata
from app.services.supplier_invoice_service import SupplierInvoiceService
router=APIRouter(prefix="/supplier-invoices",tags=["Supplier Invoices"])
def access(user):
    if not {r.name for r in user.roles}.intersection({"FINANCE","ADMIN"}):raise HTTPException(403,"Finance access required")
def get(db,id):
    x=db.get(SupplierInvoice,id)
    if not x:raise HTTPException(404,"Supplier invoice not found")
    return x
def result(db,x,user):
    svc=SupplierInvoiceService(db);data=svc.serialize(svc.attach_journal(x));data.update(document_context(db,"SUPPLIER_INVOICE",x.id,x.status,user));data["allowed_actions"]={"can_edit":x.status=="DRAFT","can_verify":x.status=="DRAFT","can_generate_journal":x.status=="VERIFIED" and not data["related_journal"],"can_void":x.status in {"DRAFT","VERIFIED"},"can_print":True,"can_manage_attachments":True,"can_view_history":True};return data
@router.get("")
def listing(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),search:str|None=None,supplier_id:int|None=None,status:str|None=None,date_from:date|None=None,date_to:date|None=None,due_from:date|None=None,due_to:date|None=None,po_number:str|None=None,receipt_number:str|None=None,source_type:str|None=None,db:Session=Depends(get_db),user=Depends(get_current_user)):
    q=db.query(SupplierInvoice)
    if search:q=q.filter(or_(SupplierInvoice.internal_invoice_number.ilike(f"%{search}%"),SupplierInvoice.supplier_invoice_number.ilike(f"%{search}%")))
    if supplier_id:q=q.filter(SupplierInvoice.supplier_id==supplier_id)
    if status:q=q.filter(SupplierInvoice.status==status)
    if date_from:q=q.filter(SupplierInvoice.invoice_date>=date_from)
    if date_to:q=q.filter(SupplierInvoice.invoice_date<=date_to)
    if due_from:q=q.filter(SupplierInvoice.due_date>=due_from)
    if due_to:q=q.filter(SupplierInvoice.due_date<=due_to)
    if po_number:q=q.join(SupplierInvoice.purchase_order).filter_by(po_number=po_number)
    if receipt_number:q=q.join(SupplierInvoice.goods_receipt).filter_by(receipt_number=receipt_number)
    if source_type:q=q.filter(SupplierInvoice.source_type==source_type)
    total=q.count();rows=q.order_by(SupplierInvoice.id.desc()).offset((page-1)*page_size).limit(page_size).all();return {"items":[SupplierInvoiceService(db).serialize(SupplierInvoiceService(db).attach_journal(x)) for x in rows],"page":page,"page_size":page_size,"total_items":total,"total_pages":ceil(total/page_size) if total else 0,"has_next":page*page_size<total,"has_previous":page>1}
@router.get("/{invoice_id}")
def detail(invoice_id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):return result(db,get(db,invoice_id),user)
@router.post("",status_code=201)
def create(data:SupplierInvoiceInput,db:Session=Depends(get_db),user=Depends(get_current_user)):access(user);return result(db,SupplierInvoiceService(db).create(data,user),user)
@router.patch("/{invoice_id}")
def update(invoice_id:int,data:SupplierInvoiceInput,db:Session=Depends(get_db),user=Depends(get_current_user)):access(user);return result(db,SupplierInvoiceService(db).update(get(db,invoice_id),data,user),user)
@router.post("/{invoice_id}/verify")
def verify(invoice_id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):access(user);return result(db,SupplierInvoiceService(db).verify(get(db,invoice_id),user),user)
@router.post("/{invoice_id}/generate-journal")
def generate(invoice_id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):access(user);j=SupplierInvoiceService(db).generate_journal(get(db,invoice_id),user);return {"id":j.id,"journal_number":j.journal_number,"status":j.status}
@router.post("/{invoice_id}/void")
def void(invoice_id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);x=get(db,invoice_id)
    if x.status=="POSTED":raise HTTPException(409,"Posted invoices cannot be voided without a reversal")
    if x.status=="VOID":raise HTTPException(409,"Invoice is already void")
    now=datetime.now(timezone.utc);x.status="VOID";x.voided_at=now
    journal=db.query(JournalEntry).filter(JournalEntry.reference_type=="SUPPLIER_INVOICE",JournalEntry.reference_id==x.id,JournalEntry.status=="DRAFT").first()
    if journal:
        journal.status="VOID";journal.voided_at=now;record_audit(db,user,"JOURNAL_VOIDED","JOURNAL_ENTRY",f"Voided {journal.journal_number}",entity_id=journal.id,reference_document=x.internal_invoice_number)
    record_audit(db,user,"SUPPLIER_INVOICE_VOIDED","SUPPLIER_INVOICE",f"Voided {x.internal_invoice_number}",entity_id=x.id);db.commit();db.refresh(x);return result(db,x,user)
@router.get("/{invoice_id}/allowed-actions")
def actions(invoice_id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):return result(db,get(db,invoice_id),user)["allowed_actions"]
@router.get("/{invoice_id}/print")
def printable(invoice_id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):return {**result(db,get(db,invoice_id),user),"document_type":"Supplier Invoice",**print_metadata(user)}
