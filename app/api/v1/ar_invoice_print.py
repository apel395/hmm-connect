from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.authorization import require_permission
from app.models.account_receivable import AccountReceivable
from app.models.ar_invoice_layout import ARInvoiceLayout
from app.models.customer import Customer
from app.services.audit import record_audit
from app.services.location_access import assigned_location_id

router = APIRouter(prefix="/ar-invoice-print", tags=["AR Invoice Print"])
view = require_permission("finance.view")
manage = require_permission("finance.manage")


class InvoiceLayout(BaseModel):
    title: str = Field(default="INVOICE", min_length=1, max_length=100)
    billing_name: str = Field(default="", max_length=200)
    billing_address: str = Field(default="", max_length=1000)
    description: str = Field(default="Invoice amount", min_length=1, max_length=500)
    payment_instructions: str = Field(default="", max_length=2000)
    footer: str = Field(default="", max_length=1000)
    show_settlement: bool = False


def consolidated(user):
    # Legacy receivables have no location dimension; never imply a scoped read.
    if assigned_location_id(user) is not None:
        raise HTTPException(403, "Legacy AR invoices require consolidated finance access")


@router.get("/{invoice_id}")
def invoice(invoice_id: int, db: Session = Depends(get_db), user=Depends(view)):
    consolidated(user)
    row = db.get(AccountReceivable, invoice_id)
    if not row:
        raise HTTPException(404, "Invoice not found")
    layout = db.get(ARInvoiceLayout, row.customer_id)
    return dict(id=row.id, invoice_number=row.invoice_number, invoice_date=row.invoice_date,
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
    row.configuration = data.model_dump()
    record_audit(db, user, "AR_INVOICE_LAYOUT_UPDATED", "CUSTOMER", f"Updated client invoice layout {customer_id}",
        entity_id=customer_id, before_data=before, after_data=row.configuration)
    db.commit()
    return row.configuration
