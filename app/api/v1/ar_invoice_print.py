from decimal import Decimal
from datetime import date
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.authorization import require_permission
from app.models.account_receivable import AccountReceivable
from app.models.ar_invoice_layout import ARInvoiceLayout
from app.models.customer import Customer
from app.models.sales_transaction import SalesTransaction
from app.models.customer_payment import CustomerPayment
from app.services.ar_invoice_service import scoped_receivables
from app.services.audit import record_audit
from app.services.location_access import assigned_location_id

router = APIRouter(prefix="/ar-invoice-print", tags=["AR Invoice Print"])
view = require_permission("finance.view")
manage = require_permission("finance.manage")


class InvoiceLayout(BaseModel):
    template: Literal["standard", "phr"] = "standard"
    company_address: str = Field(default="", max_length=1000)
    attention: str = Field(default="Finance & Accounting Dept.", max_length=200)
    contract_number: str = Field(default="", max_length=100)
    contract_date: date | None = None
    signer_name: str = Field(default="", max_length=200)
    signer_position: str = Field(default="", max_length=200)
    title: str = Field(default="INVOICE", min_length=1, max_length=100)
    billing_name: str = Field(default="", max_length=200)
    billing_address: str = Field(default="", max_length=1000)
    description: str = Field(default="Invoice amount", min_length=1, max_length=500)
    payment_instructions: str = Field(default="", max_length=2000)
    footer: str = Field(default="", max_length=1000)
    show_settlement: bool = False


class ServiceLine(BaseModel):
    registration_number: str = Field(default="", max_length=150)
    description: str = Field(min_length=1, max_length=1000)
    amount: Decimal = Field(ge=0, max_digits=18, decimal_places=2)


class InvoiceDocument(BaseModel):
    description: str = Field(default="", max_length=1000)
    contract_number: str = Field(default="", max_length=100)
    contract_date: date | None = None
    lines: list[ServiceLine] = Field(default_factory=list, max_length=200)
    tax_label: str = Field(default="Tax", max_length=150)
    tax_amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=2)
    amount_in_words: str = Field(default="", max_length=1000)

    def total(self):
        return sum((line.amount for line in self.lines), Decimal("0")) + self.tax_amount


def consolidated(user):
    # Legacy receivables have no location dimension; never imply a scoped read.
    if assigned_location_id(user) is not None:
        raise HTTPException(403, "Legacy AR invoices require consolidated finance access")


@router.get("/{invoice_id}")
def invoice(invoice_id: int, db: Session = Depends(get_db), user=Depends(view)):
    row = scoped_receivables(db,user).filter_by(id=invoice_id).first()
    if not row:
        raise HTTPException(404, "Invoice not found")
    layout = db.get(ARInvoiceLayout, row.customer_id)
    config = layout.configuration if layout else {}
    saved = config.get("invoice_documents", {}).get(str(row.id))
    source = db.get(SalesTransaction,row.source_sale_id) if row.source_sale_id else None
    if saved is None and source:
        source_lines = sorted(source.lines,key=lambda line:line.line_number or line.id)
        subtotal=Decimal(source.subtotal or 0);discount=Decimal(source.discount_amount or 0);allocated=Decimal(0)
        lines=[]
        for index,line in enumerate(source_lines):
            share=min(discount-allocated,(discount*Decimal(line.line_amount)/subtotal).quantize(Decimal('.01'))) if subtotal else Decimal(0)
            if index==len(source_lines)-1:share=discount-allocated
            allocated+=share
            lines.append(ServiceLine(description=line.product.name if line.product else 'Service',amount=Decimal(line.line_amount)-share+Decimal(line.service_charge_amount or 0)))
        document=InvoiceDocument(lines=lines,tax_label='PBJT' if any(line.tax_type=='PBJT' for line in source_lines) else 'Tax',tax_amount=source.tax_amount)
    else:
        document = InvoiceDocument(**(saved or {}))
    receipts=[{"id":payment.id,"payment_number":payment.payment_number,"payment_date":payment.payment_date,"amount":payment.amount,"payment_method":payment.payment_method,"reference_number":payment.reference_number,"journal_entry_id":payment.journal_entry_id} for payment in db.query(CustomerPayment).filter_by(account_receivable_id=row.id,status="POSTED").order_by(CustomerPayment.id).all()]
    return dict(receipts=receipts,document=document.model_dump(mode="json"),
        source_sale_id=row.source_sale_id, account_id=row.account_id, location_id=row.location_id,
        print_ready=(document.total() == Decimal(str(row.amount)) and bool(document.lines)), id=row.id, invoice_number=row.invoice_number, invoice_date=row.invoice_date,
        due_date=row.due_date, amount=row.amount, received_amount=row.received_amount,
        outstanding_amount=row.outstanding_amount, customer_id=row.customer_id,
        customer_name=row.customer.customer_name, customer_address=row.customer.address,
        layout=InvoiceLayout(**(layout.configuration if layout else {})).model_dump())


@router.put("/clients/{customer_id}")
def update_layout(customer_id: int, data: InvoiceLayout, db: Session = Depends(get_db), user=Depends(manage)):
    consolidated(user)
    if not db.get(Customer, customer_id):
        raise HTTPException(404, "Customer not found")
    row = db.query(ARInvoiceLayout).filter_by(customer_id=customer_id).with_for_update().first()
    before = row.configuration if row else None
    if not row:
        row = ARInvoiceLayout(customer_id=customer_id)
        db.add(row)
    row.configuration = {**data.model_dump(mode="json"), "invoice_documents": (before or {}).get("invoice_documents", {})}
    record_audit(db, user, "AR_INVOICE_LAYOUT_UPDATED", "CUSTOMER", f"Updated client invoice layout {customer_id}",
        entity_id=customer_id, before_data=before, after_data=row.configuration)
    db.commit()
    return row.configuration


@router.put("/{invoice_id}/document")
def update_document(invoice_id: int, data: InvoiceDocument, db: Session = Depends(get_db), user=Depends(manage)):
    invoice_row = scoped_receivables(db,user).filter_by(id=invoice_id).first()
    if not invoice_row:
        raise HTTPException(404, "Invoice not found")
    if not data.lines or data.total() != Decimal(str(invoice_row.amount)):
        raise HTTPException(422, "Service amounts plus tax must equal the AR invoice amount")
    row = db.query(ARInvoiceLayout).filter_by(customer_id=invoice_row.customer_id).with_for_update().first()
    if not row:
        row = ARInvoiceLayout(customer_id=invoice_row.customer_id, configuration={})
        db.add(row)
    config = dict(row.configuration or {})
    documents = dict(config.get("invoice_documents", {}))
    before = documents.get(str(invoice_id))
    documents[str(invoice_id)] = data.model_dump(mode="json")
    row.configuration = {**config, "invoice_documents": documents}
    record_audit(db, user, "AR_INVOICE_DOCUMENT_UPDATED", "ACCOUNT_RECEIVABLE",
        f"Updated print details for invoice {invoice_id}", entity_id=invoice_id,
        before_data=before, after_data=documents[str(invoice_id)])
    db.commit()
    return documents[str(invoice_id)]
