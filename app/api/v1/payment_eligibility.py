from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_any_role
from app.models.payment import Payment, PaymentAllocation
from app.models.supplier_invoice import SupplierInvoice

router = APIRouter(prefix="/payments", tags=["Payments"])
ZERO = Decimal("0")


def access(user):
    if not has_any_role(user, "FINANCE"):
        raise HTTPException(status_code=403, detail="Finance access required")


@router.get("/eligible-invoices-available")
def eligible_invoices_available(
    supplier_id: int,
    currency: str = "IDR",
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    access(user)

    reserved_rows = (
        db.query(
            PaymentAllocation.supplier_invoice_id,
            func.coalesce(func.sum(PaymentAllocation.allocated_amount), 0),
        )
        .join(Payment, Payment.id == PaymentAllocation.payment_id)
        .filter(Payment.status == "APPROVED")
        .group_by(PaymentAllocation.supplier_invoice_id)
        .all()
    )
    reserved_by_invoice = {
        invoice_id: Decimal(amount or 0)
        for invoice_id, amount in reserved_rows
    }

    invoices = (
        db.query(SupplierInvoice)
        .filter(
            SupplierInvoice.supplier_id == supplier_id,
            SupplierInvoice.currency == currency.upper(),
            SupplierInvoice.status.in_(("VERIFIED", "POSTED")),
            SupplierInvoice.balance_amount > 0,
        )
        .order_by(SupplierInvoice.due_date.asc().nullslast(), SupplierInvoice.id.asc())
        .all()
    )

    result = []
    for invoice in invoices:
        balance = Decimal(invoice.balance_amount or 0)
        reserved = reserved_by_invoice.get(invoice.id, ZERO)
        available = max(ZERO, balance - reserved)
        if available <= 0:
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
            "reserved_amount": reserved,
            "available_balance": available,
            "currency": invoice.currency,
            "business_unit_id": invoice.business_unit_id,
            "location_id": invoice.location_id,
            "department_id": invoice.department_id,
            "status": invoice.status,
            "payment_status": invoice.payment_status,
        })

    return result
