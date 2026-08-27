from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_permission
from app.models.supplier_invoice import SupplierInvoice
from app.services.supplier_invoice_accounting import accounting_state
from app.services.location_access import apply_location_scope

router = APIRouter(prefix="/ap-reconciliation", tags=["Accounts Payable"])


def access(user):
    if not has_permission(user, "finance.view"):
        raise HTTPException(403, "Finance access required")


@router.get("/exceptions")
def exceptions(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    access(user)
    invoices = apply_location_scope(
        db.query(SupplierInvoice), SupplierInvoice, user
    ).order_by(SupplierInvoice.id.desc()).all()
    rows = []
    for invoice in invoices:
        state = accounting_state(db, invoice)
        if not state["accounting_exception"]:
            continue
        rows.append({
            "invoice_id": invoice.id,
            "internal_invoice_number": invoice.internal_invoice_number,
            "supplier_invoice_number": invoice.supplier_invoice_number,
            "supplier_id": invoice.supplier_id,
            "supplier_name": invoice.supplier.name if invoice.supplier else None,
            "total_amount": invoice.total_amount,
            **state,
        })
    return {
        "exception_count": len(rows),
        "items": rows,
    }
