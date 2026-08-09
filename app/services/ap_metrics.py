from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session, joinedload

from app.models.journal_entry import JournalEntry
from app.models.supplier_invoice import SupplierInvoice

ZERO = Decimal("0")


def open_invoice_query(
    db: Session,
    *,
    business_unit_id: int | None = None,
    location_id: int | None = None,
    department_id: int | None = None,
):
    query = (
        db.query(SupplierInvoice)
        .join(
            JournalEntry,
            (JournalEntry.reference_type == "SUPPLIER_INVOICE")
            & (JournalEntry.reference_id == SupplierInvoice.id)
            & (JournalEntry.status == "POSTED"),
        )
        .options(joinedload(SupplierInvoice.supplier))
        .filter(SupplierInvoice.balance_amount > 0)
        .distinct()
    )
    if business_unit_id:
        query = query.filter(SupplierInvoice.business_unit_id == business_unit_id)
    if location_id:
        query = query.filter(SupplierInvoice.location_id == location_id)
    if department_id:
        query = query.filter(SupplierInvoice.department_id == department_id)
    return query


def ap_metrics(
    db: Session,
    *,
    as_of_date: date,
    business_unit_id: int | None = None,
    location_id: int | None = None,
    department_id: int | None = None,
):
    invoices = open_invoice_query(
        db,
        business_unit_id=business_unit_id,
        location_id=location_id,
        department_id=department_id,
    ).all()

    result = {
        "total_outstanding_ap": ZERO,
        "overdue_ap": ZERO,
        "due_today": ZERO,
        "due_next_7_days": ZERO,
        "due_next_30_days": ZERO,
        "unpaid_invoice_count": 0,
        "partially_paid_invoice_count": 0,
        "overdue_invoice_count": 0,
        "open_invoice_count": len(invoices),
        "urgent_invoices": [],
    }

    urgent = []
    for invoice in invoices:
        amount = Decimal(invoice.balance_amount or 0)
        result["total_outstanding_ap"] += amount
        if invoice.payment_status == "UNPAID":
            result["unpaid_invoice_count"] += 1
        elif invoice.payment_status == "PARTIALLY_PAID":
            result["partially_paid_invoice_count"] += 1

        if invoice.due_date:
            if invoice.due_date < as_of_date:
                result["overdue_ap"] += amount
                result["overdue_invoice_count"] += 1
            elif invoice.due_date == as_of_date:
                result["due_today"] += amount
            elif invoice.due_date <= as_of_date + timedelta(days=7):
                result["due_next_7_days"] += amount
            elif invoice.due_date <= as_of_date + timedelta(days=30):
                result["due_next_30_days"] += amount

            if invoice.due_date <= as_of_date + timedelta(days=7):
                urgent.append({
                    "invoice_id": invoice.id,
                    "internal_invoice_number": invoice.internal_invoice_number,
                    "supplier_invoice_number": invoice.supplier_invoice_number,
                    "supplier": invoice.supplier.name if invoice.supplier else None,
                    "due_date": invoice.due_date,
                    "outstanding_balance": amount,
                    "days_overdue": max((as_of_date - invoice.due_date).days, 0),
                    "status": invoice.payment_status,
                })

    urgent.sort(key=lambda row: (row["due_date"], -row["outstanding_balance"]))
    result["urgent_invoices"] = urgent[:10]
    return result, invoices
