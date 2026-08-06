from datetime import datetime, timezone
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models.accounting_posting_rule import AccountingPostingRule
from app.models.chart_of_account import ChartOfAccount
from app.models.goods_receipt import GoodsReceipt
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.purchase_order import PurchaseOrder
from app.models.supplier import Supplier
from app.models.supplier_invoice import SupplierInvoice, SupplierInvoiceLine
from app.schemas.supplier_invoice import SupplierInvoiceInput
from app.services.document_number import next_document_number
from app.services.audit import record_audit

class SupplierInvoiceService:
    def __init__(self,db:Session): self.db=db
    @staticmethod
    def serialize(x):
        journal=next((j for j in getattr(x,"_journals",[]) if j.reference_type=="SUPPLIER_INVOICE"),None)
        return {"id":x.id,"internal_invoice_number":x.internal_invoice_number,"supplier_invoice_number":x.supplier_invoice_number,"supplier_id":x.supplier_id,"supplier_name":x.supplier.name,"invoice_date":x.invoice_date,"received_date":x.received_date,"due_date":x.due_date,"purchase_order_id":x.purchase_order_id,"purchase_order_number":x.purchase_order.po_number if x.purchase_order else None,"goods_receipt_id":x.goods_receipt_id,"receipt_number":x.goods_receipt.receipt_number if x.goods_receipt else None,"department_id":x.department_id,"department_name":x.department.name if x.department else None,"location_id":x.location_id,"location_name":x.location.name if x.location else None,"currency":x.currency,"subtotal":x.subtotal,"discount_amount":x.discount_amount,"tax_amount":x.tax_amount,"withholding_tax_amount":x.withholding_tax_amount,"total_amount":x.total_amount,"paid_amount":x.paid_amount,"balance_amount":x.balance_amount,"payment_status":x.payment_status,"status":x.status,"notes":x.notes,"source_type":x.source_type,"created_by_name":x.created_by.full_name if x.created_by else None,"created_at":x.created_at,"updated_at":x.updated_at,"verified_at":x.verified_at,"posted_at":x.posted_at,"voided_at":x.voided_at,"related_journal":{"id":journal.id,"journal_number":journal.journal_number,"status":journal.status} if journal else None,"lines":[{"id":l.id,"product_id":l.product_id,"product_code":l.product.code if l.product else None,"product_name":l.product.name if l.product else None,"purchase_order_item_id":l.purchase_order_item_id,"goods_receipt_item_id":l.goods_receipt_item_id,"description":l.description,"quantity":l.quantity,"uom":l.uom,"unit_price":l.unit_price,"line_amount":l.line_amount,"account_id":l.account_id,"account_code":l.account.account_number if l.account else None,"account_name":l.account.account_name if l.account else None,"department_id":l.department_id,"notes":l.notes} for l in x.lines]}
    def attach_journal(self,x): x._journals=self.db.query(JournalEntry).filter(JournalEntry.reference_type=="SUPPLIER_INVOICE",JournalEntry.reference_id==x.id).all(); return x
    def validate(self,data:SupplierInvoiceInput,exclude_id=None):
        from app.services.organization_dimensions import validate_dimensions
        validate_dimensions(self.db,data.business_unit_id,data.location_id,data.department_id,True)
        if not self.db.get(Supplier,data.supplier_id): raise HTTPException(404,"Supplier not found")
        q=self.db.query(SupplierInvoice).filter(SupplierInvoice.supplier_id==data.supplier_id,func.lower(SupplierInvoice.supplier_invoice_number)==data.supplier_invoice_number.strip().lower())
        if exclude_id:q=q.filter(SupplierInvoice.id!=exclude_id)
        if q.first():raise HTTPException(409,"Supplier invoice number already exists for this supplier")
        po=self.db.get(PurchaseOrder,data.purchase_order_id) if data.purchase_order_id else None
        receipt=self.db.get(GoodsReceipt,data.goods_receipt_id) if data.goods_receipt_id else None
        if data.purchase_order_id and (not po or po.supplier_id!=data.supplier_id): raise HTTPException(400,"Purchase order does not belong to selected supplier")
        if receipt and (receipt.purchase_order.supplier_id!=data.supplier_id): raise HTTPException(400,"Receipt does not belong to selected supplier")
        if receipt and po and receipt.purchase_order_id!=po.id: raise HTTPException(400,"Receipt does not belong to selected purchase order")
        subtotal=sum((l.quantity*l.unit_price for l in data.lines),Decimal("0")); total=subtotal-data.discount_amount+data.tax_amount-data.withholding_tax_amount
        if data.total_amount is not None and data.total_amount!=total: raise HTTPException(400,"Invoice total does not match line totals and adjustments")
        return subtotal,total
    def create(self,data,user):
        subtotal,total=self.validate(data); x=SupplierInvoice(internal_invoice_number=next_document_number(self.db,"INV"),supplier_invoice_number=data.supplier_invoice_number.strip(),supplier_id=data.supplier_id,invoice_date=data.invoice_date,received_date=data.received_date,due_date=data.due_date,purchase_order_id=data.purchase_order_id,goods_receipt_id=data.goods_receipt_id,business_unit_id=data.business_unit_id,department_id=data.department_id,location_id=data.location_id,currency=data.currency.upper(),subtotal=subtotal,discount_amount=data.discount_amount,tax_amount=data.tax_amount,withholding_tax_amount=data.withholding_tax_amount,total_amount=total,balance_amount=total,status="DRAFT",notes=data.notes,source_type=data.source_type,created_by_id=user.id)
        for l in data.lines:x.lines.append(SupplierInvoiceLine(**l.model_dump(),line_amount=l.quantity*l.unit_price))
        self.db.add(x);self.db.flush();record_audit(self.db,user,"SUPPLIER_INVOICE_CREATED","SUPPLIER_INVOICE",f"Created {x.internal_invoice_number}",entity_id=x.id);self.db.commit();self.db.refresh(x);return self.attach_journal(x)
    def update(self,x,data,user):
        if x.status!="DRAFT":raise HTTPException(409,"Only draft invoices can be edited")
        subtotal,total=self.validate(data,x.id)
        for key,value in data.model_dump(exclude={"lines","total_amount"}).items():setattr(x,key,value)
        x.subtotal=subtotal;x.total_amount=total;x.lines.clear()
        for l in data.lines:x.lines.append(SupplierInvoiceLine(**l.model_dump(),line_amount=l.quantity*l.unit_price))
        record_audit(self.db,user,"SUPPLIER_INVOICE_UPDATED","SUPPLIER_INVOICE",f"Updated {x.internal_invoice_number}",entity_id=x.id);self.db.commit();self.db.refresh(x);return self.attach_journal(x)
    def verify(self,x,user):
        if x.status!="DRAFT":raise HTTPException(409,"Only draft invoices can be verified")
        x.status="VERIFIED";x.verified_at=datetime.now(timezone.utc);record_audit(self.db,user,"SUPPLIER_INVOICE_VERIFIED","SUPPLIER_INVOICE",f"Verified {x.internal_invoice_number}",entity_id=x.id);self.db.commit();self.db.refresh(x);return self.attach_journal(x)
    def generate_journal(self,x,user):
        if x.status!="VERIFIED":raise HTTPException(409,"Invoice must be verified before journal generation")
        existing=self.db.query(JournalEntry).filter(JournalEntry.reference_type=="SUPPLIER_INVOICE",JournalEntry.reference_id==x.id,JournalEntry.status!="VOID").first()
        if existing:return existing
        event="SUPPLIER_INVOICE_INVENTORY" if x.goods_receipt and x.goods_receipt.destination_type=="WAREHOUSE" else "SUPPLIER_INVOICE_DIRECT_USE"
        rule=self.db.query(AccountingPostingRule).filter(AccountingPostingRule.event_type==event,AccountingPostingRule.is_active.is_(True)).first()
        if not rule:raise HTTPException(409,f"No active posting rule configured for {event}")
        grouped={}
        for line in x.lines:
            account_id=line.account_id or rule.debit_account_id; account=self.db.get(ChartOfAccount,account_id)
            if not account or not account.is_active or not account.is_posting:raise HTTPException(409,"Invoice line requires a valid active posting account")
            grouped[account_id]=grouped.get(account_id,Decimal("0"))+line.line_amount
        credit_account=rule.credit_account
        if not credit_account.is_active or not credit_account.is_posting:raise HTTPException(409,"Accounts Payable posting account is invalid")
        journal=JournalEntry(journal_number=next_document_number(self.db,"JV",digits=4),posting_date=x.invoice_date,status="DRAFT",document_type="SUPPLIER_INVOICE",document_number=x.internal_invoice_number,reference_type="SUPPLIER_INVOICE",reference_id=x.id,description=f"Supplier invoice {x.supplier_invoice_number}",created_by_id=user.id,posted_at=None)
        for i,(account_id,amount) in enumerate(grouped.items(),1):journal.lines.append(JournalLine(line_number=i,account_id=account_id,debit=amount,credit=0,description=x.notes,department_id=x.department_id,location_id=x.location_id,supplier_id=x.supplier_id))
        journal.lines.append(JournalLine(line_number=len(grouped)+1,account_id=rule.credit_account_id,debit=0,credit=x.subtotal,description=f"Payable to {x.supplier.name}",department_id=x.department_id,location_id=x.location_id,supplier_id=x.supplier_id))
        # Adjustments must be assigned explicitly in this first patch.
        if x.total_amount!=x.subtotal:raise HTTPException(409,"Discount and tax account configuration is not available; journal cannot be generated")
        self.db.add(journal);self.db.flush();record_audit(self.db,user,"JOURNAL_GENERATED","JOURNAL_ENTRY",f"Generated {journal.journal_number}",entity_id=journal.id,reference_document=x.internal_invoice_number);self.db.commit();self.db.refresh(journal);return journal
