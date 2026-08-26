from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_any_role
from app.models.journal_entry import JournalEntry
from app.models.payment import Payment, PaymentAllocation
from app.models.supplier import Supplier
from app.models.supplier_invoice import SupplierInvoice
from app.services.location_access import apply_location_scope
from app.services.payable_balance import invoice_balance

router = APIRouter(prefix="/payments", tags=["Payments"])
ZERO = Decimal("0")


def access(user):
    if not has_any_role(user, "FINANCE"):
        raise HTTPException(status_code=403, detail="Finance access required")


def reserved_by_invoice(db: Session) -> dict[int, Decimal]:
    rows = (
        db.query(
            PaymentAllocation.supplier_invoice_id,
            func.coalesce(func.sum(PaymentAllocation.allocated_amount), 0),
        )
        .join(Payment, Payment.id == PaymentAllocation.payment_id)
        .filter(Payment.status == "APPROVED")
        .group_by(PaymentAllocation.supplier_invoice_id)
        .all()
    )
    return {
        invoice_id: Decimal(amount or 0)
        for invoice_id, amount in rows
    }


@router.get("/eligible-suppliers")
def eligible_suppliers(
    currency: str = "IDR",
    include_supplier_id: int | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Return only suppliers that currently have an amount available to pay.

    The eligibility matches the payment invoice flow: invoice must be POSTED,
    visible to the user's location scope, have an outstanding balance, and not
    be fully reserved by an APPROVED payment.  include_supplier_id preserves
    the current supplier while editing an existing draft payment.
    """
    access(user)
    currency = currency.upper()
    reserved = reserved_by_invoice(db)

    invoices = (
        apply_location_scope(db.query(SupplierInvoice), SupplierInvoice, user)
        .filter(
            SupplierInvoice.currency == currency,
            SupplierInvoice.status == "POSTED",
        )
        .order_by(SupplierInvoice.supplier_id.asc(), SupplierInvoice.id.asc())
        .all()
    )

    supplier_ids: set[int] = set()
    for invoice in invoices:
        outstanding = invoice_balance(invoice)
        if outstanding <= ZERO:
            continue
        available = max(ZERO, outstanding - reserved.get(invoice.id, ZERO))
        if available > ZERO:
            supplier_ids.add(invoice.supplier_id)

    if include_supplier_id:
        supplier_ids.add(include_supplier_id)

    if not supplier_ids:
        return []

    suppliers = (
        db.query(Supplier)
        .filter(Supplier.id.in_(supplier_ids))
        .order_by(Supplier.name.asc(), Supplier.code.asc())
        .all()
    )
    return [
        {
            "id": supplier.id,
            "code": supplier.code,
            "name": supplier.name,
            "is_active": supplier.is_active,
        }
        for supplier in suppliers
        if supplier.is_active or supplier.id == include_supplier_id
    ]


@router.get("/eligible-invoices-available")
def eligible_invoices_available(
    supplier_id: int,
    currency: str = "IDR",
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    access(user)

    reserved = reserved_by_invoice(db)

    invoices = (
        db.query(SupplierInvoice)
        .join(
            JournalEntry,
            (JournalEntry.reference_type == "SUPPLIER_INVOICE")
            & (JournalEntry.reference_id == SupplierInvoice.id)
            & (JournalEntry.status == "POSTED"),
        )
        .filter(
            SupplierInvoice.supplier_id == supplier_id,
            SupplierInvoice.currency == currency.upper(),
        )
        .distinct()
        .order_by(SupplierInvoice.due_date.asc().nullslast(), SupplierInvoice.id.asc())
        .all()
    )

    result = []
    for invoice in invoices:
        balance = invoice_balance(invoice)
        if balance <= ZERO:
            continue
        reserved_amount = reserved.get(invoice.id, ZERO)
        available = max(ZERO, balance - reserved_amount)
        if available <= ZERO:
            continue
        result.append({
            "id": invoice.id,
            "invoice_number": invoice.internal_invoice_number,
            "supplier_invoice_number": invoice.supplier_invoice_number,
            "invoice_date": invoice.invoice_date,
            "due_date": invoice.due_date,
            "total_amount": invoice.total_amount,
            "paid_amount": invoice.paid_amount,
            "outstanding_balance": balance,
            "reserved_amount": reserved_amount,
            "available_balance": available,
            "currency": invoice.currency,
            "business_unit_id": invoice.business_unit_id,
            "location_id": invoice.location_id,
            "department_id": invoice.department_id,
            "status": invoice.status,
            "posting_status": "POSTED",
            "payment_status": invoice.payment_status,
        })

    return result
