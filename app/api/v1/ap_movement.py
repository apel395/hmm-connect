from datetime import date
from decimal import Decimal
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_permission, is_superuser, role_names
from app.models.payment import Payment
from app.models.supplier_adjustment import SupplierAdjustment
from app.models.supplier_invoice import SupplierInvoice
from app.services.location_access import apply_location_scope, resolve_location_id

router = APIRouter(prefix="/ap-movement", tags=["Accounts Payable Movement"])
ZERO = Decimal("0.00")


@router.get("")
def listing(
    date_from: date | None = None,
    date_to: date | None = None,
    supplier_id: int | None = None,
    location_id: int | None = None,
    movement_type: str | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if not has_permission(user, "ap.view"):
        raise HTTPException(403, "AP access required")
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "From date must not exceed To date")
    if movement_type and movement_type not in {"INVOICE", "PAYMENT", "ADJUSTMENT", "OPENING"}:
        raise HTTPException(422, "Invalid movement type")
    location_id = resolve_location_id(user, location_id)
    token = (search or "").strip().lower()
    ap_only = "AP" in role_names(user) and not is_superuser(user)

    invoices = apply_location_scope(
        db.query(SupplierInvoice).filter(SupplierInvoice.status == "POSTED"),
        SupplierInvoice, user,
    )
    payments = apply_location_scope(
        db.query(Payment).filter(Payment.status == "POSTED"), Payment, user,
    )
    adjustments = apply_location_scope(
        db.query(SupplierAdjustment).filter(SupplierAdjustment.status == "POSTED"),
        SupplierAdjustment, user,
    )
    if ap_only:
        payments = payments.filter(Payment.created_by_id == user.id)
    if location_id:
        invoices = invoices.filter(SupplierInvoice.location_id == location_id)
        payments = payments.filter(Payment.location_id == location_id)
        adjustments = adjustments.filter(SupplierAdjustment.location_id == location_id)
    if supplier_id:
        invoices = invoices.filter(SupplierInvoice.supplier_id == supplier_id)
        payments = payments.filter(Payment.supplier_id == supplier_id)
        adjustments = adjustments.filter(SupplierAdjustment.supplier_id == supplier_id)

    rows = []
    for invoice in invoices.all():
        rows.append({
            "id": f"INVOICE-{invoice.id}", "movement_date": invoice.invoice_date,
            "supplier_id": invoice.supplier_id,
            "supplier_name": invoice.supplier.name if invoice.supplier else None,
            "document_type": "SUPPLIER_INVOICE", "document_id": invoice.id,
            "document_number": invoice.internal_invoice_number,
            "supplier_reference": invoice.supplier_invoice_number,
            "movement_type": "INVOICE", "increase": Decimal(invoice.total_amount or 0),
            "decrease": ZERO, "status": invoice.status,
        })
    for payment in payments.all():
        rows.append({
            "id": f"PAYMENT-{payment.id}", "movement_date": payment.payment_date,
            "supplier_id": payment.supplier_id,
            "supplier_name": payment.supplier.name if payment.supplier else None,
            "document_type": "SUPPLIER_PAYMENT", "document_id": payment.id,
            "document_number": payment.payment_number,
            "supplier_reference": payment.reference_number,
            "movement_type": "PAYMENT", "increase": ZERO,
            "decrease": Decimal(payment.total_amount or 0), "status": payment.status,
        })
    for adjustment in adjustments.all():
        rows.append({
            "id": f"ADJUSTMENT-{adjustment.id}", "movement_date": adjustment.adjustment_date,
            "supplier_id": adjustment.supplier_id,
            "supplier_name": adjustment.supplier.name if adjustment.supplier else None,
            "document_type": "SUPPLIER_ADJUSTMENT", "document_id": adjustment.id,
            "document_number": adjustment.adjustment_number,
            "supplier_reference": adjustment.reason,
            "movement_type": "ADJUSTMENT", "increase": ZERO,
            "decrease": Decimal(adjustment.amount or 0), "status": adjustment.status,
        })
    rows.sort(key=lambda row: (row["movement_date"], str(row["id"])))
    opening = sum(
        (row["increase"] - row["decrease"] for row in rows
         if date_from and row["movement_date"] < date_from), ZERO,
    )
    period = [
        row for row in rows
        if (not date_from or row["movement_date"] >= date_from)
        and (not date_to or row["movement_date"] <= date_to)
    ]
    invoice_total = sum((r["increase"] for r in period if r["movement_type"] == "INVOICE"), ZERO)
    payment_total = sum((r["decrease"] for r in period if r["movement_type"] == "PAYMENT"), ZERO)
    adjustment_total = sum((r["decrease"] for r in period if r["movement_type"] == "ADJUSTMENT"), ZERO)
    balance = opening
    for row in period:
        balance += row["increase"] - row["decrease"]
        row["running_balance"] = balance
    closing = balance
    if movement_type:
        period = [row for row in period if row["movement_type"] == movement_type]
    if token:
        period = [
            row for row in period if any(
                token in str(row.get(key) or "").lower()
                for key in ("document_number", "supplier_reference", "supplier_name")
            )
        ]
    total = len(period)
    return {
        "items": period[(page - 1) * page_size:page * page_size],
        "page": page, "page_size": page_size, "total_items": total,
        "total_pages": ceil(total / page_size) if total else 0,
        "has_next": page * page_size < total, "has_previous": page > 1,
        "summary": {
            "opening_balance": opening, "invoice_total": invoice_total,
            "payment_total": payment_total, "adjustment_total": adjustment_total,
            "closing_balance": closing,
        },
    }
