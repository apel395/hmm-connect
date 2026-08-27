from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_permission
from app.models.journal_entry import JournalEntry
from app.models.payment import Payment, PaymentAllocation
from app.models.supplier_invoice import SupplierInvoice
from app.services.ap_metrics import ZERO, ap_metrics
from app.services.document_context import print_metadata
from app.services.location_access import resolve_location_id

router = APIRouter(prefix="/ap-aging", tags=["Accounts Payable"])
BUCKETS = ("current", "1_30", "31_60", "61_90", "over_90")


def _bucket(days_overdue: int) -> str:
    if days_overdue <= 0:
        return "current"
    if days_overdue <= 30:
        return "1_30"
    if days_overdue <= 60:
        return "31_60"
    if days_overdue <= 90:
        return "61_90"
    return "over_90"


def _print_bucket(days_overdue: int) -> str:
    if days_overdue <= 30:
        return "0_30"
    if days_overdue <= 60:
        return "31_60"
    if days_overdue <= 90:
        return "61_90"
    if days_overdue <= 120:
        return "91_120"
    return "over_120"


def _posted_payment_facts(db: Session, location_id: int | None = None) -> dict[int, dict]:
    rows = (
        db.query(
            PaymentAllocation.supplier_invoice_id,
            func.coalesce(func.sum(PaymentAllocation.allocated_amount), 0),
            func.max(Payment.payment_date),
        )
        .join(Payment, Payment.id == PaymentAllocation.payment_id)
        .join(SupplierInvoice, SupplierInvoice.id == PaymentAllocation.supplier_invoice_id)
        .filter(Payment.status == "POSTED")
        .filter(SupplierInvoice.location_id == location_id if location_id is not None else True)
        .group_by(PaymentAllocation.supplier_invoice_id)
        .all()
    )
    return {
        invoice_id: {
            "paid_amount": Decimal(paid_amount or 0),
            "last_payment_date": last_payment_date,
        }
        for invoice_id, paid_amount, last_payment_date in rows
    }


def _aging_data(db: Session, location_id: int | None = None):
    today = date.today()
    metrics, invoices = ap_metrics(db, as_of_date=today, location_id=location_id)
    posted_payment_facts = _posted_payment_facts(db, location_id)

    totals = {key: ZERO for key in BUCKETS}
    counts = {key: 0 for key in BUCKETS}
    suppliers = {key: set() for key in BUCKETS}
    report = []
    weighted_days = ZERO
    weighted_amount = ZERO
    supplier_totals: dict[int, dict] = {}

    for invoice in invoices:
        total_amount = Decimal(invoice.total_amount or 0)
        paid_amount = Decimal(invoice.paid_amount or 0)
        outstanding = Decimal(invoice.balance_amount or 0)
        days = (today - invoice.due_date).days if invoice.due_date else 0
        bucket = _bucket(days)
        values = {key: ZERO for key in BUCKETS}
        values[bucket] = outstanding
        totals[bucket] += outstanding
        counts[bucket] += 1
        suppliers[bucket].add(invoice.supplier_id)

        if days > 0:
            weighted_days += outstanding * days
            weighted_amount += outstanding

        supplier = supplier_totals.setdefault(invoice.supplier_id, {
            "supplier_id": invoice.supplier_id,
            "supplier_name": invoice.supplier.name if invoice.supplier else None,
            "outstanding": ZERO,
            "invoice_count": 0,
            "overdue": ZERO,
        })
        supplier["outstanding"] += outstanding
        supplier["invoice_count"] += 1
        if days > 0:
            supplier["overdue"] += outstanding

        report.append({
            "id": invoice.id,
            "supplier_invoice_id": invoice.id,
            "invoice_number": invoice.internal_invoice_number,
            "supplier_invoice_number": invoice.supplier_invoice_number,
            "supplier_id": invoice.supplier_id,
            "supplier_name": invoice.supplier.name if invoice.supplier else None,
            "invoice_date": invoice.invoice_date,
            "due_date": invoice.due_date,
            "amount": total_amount,
            "paid_amount": paid_amount,
            "adjustment_amount": Decimal(invoice.adjustment_amount or 0),
            "outstanding": outstanding,
            "payment_status": invoice.payment_status,
            "days_overdue": max(days, 0),
            "aging_bucket": bucket,
            **values,
        })

    total_outstanding = sum(totals.values(), ZERO)
    overdue_total = sum((totals[key] for key in BUCKETS if key != "current"), ZERO)
    bucket_summary = {
        key: {
            "amount": totals[key],
            "invoice_count": counts[key],
            "supplier_count": len(suppliers[key]),
            "percentage": float((totals[key] / total_outstanding * 100) if total_outstanding else ZERO),
        }
        for key in BUCKETS
    }
    top_suppliers = sorted(supplier_totals.values(), key=lambda row: row["outstanding"], reverse=True)[:10]

    paid_invoices = (
        db.query(SupplierInvoice)
        .join(
            JournalEntry,
            (JournalEntry.reference_type == "SUPPLIER_INVOICE")
            & (JournalEntry.reference_id == SupplierInvoice.id)
            & (JournalEntry.status == "POSTED"),
        )
        .join(PaymentAllocation, PaymentAllocation.supplier_invoice_id == SupplierInvoice.id)
        .join(Payment, Payment.id == PaymentAllocation.payment_id)
        .filter(Payment.status == "POSTED")
        .filter(SupplierInvoice.location_id == location_id if location_id is not None else True)
        .distinct()
        .order_by(SupplierInvoice.id.desc())
        .all()
    )

    paid_rows = []
    for invoice in paid_invoices:
        payment = posted_payment_facts.get(invoice.id)
        if not payment:
            continue
        total_amount = Decimal(invoice.total_amount or 0)
        paid_amount = Decimal(payment["paid_amount"] or 0)
        adjustment_amount = Decimal(invoice.adjustment_amount or 0)
        outstanding = max(ZERO, total_amount - paid_amount - adjustment_amount)
        payment_status = "PAID" if outstanding == ZERO else "PARTIALLY_PAID"
        paid_rows.append({
            "id": invoice.id,
            "supplier_invoice_id": invoice.id,
            "invoice_number": invoice.internal_invoice_number,
            "supplier_invoice_number": invoice.supplier_invoice_number,
            "supplier_id": invoice.supplier_id,
            "supplier_name": invoice.supplier.name if invoice.supplier else None,
            "invoice_date": invoice.invoice_date,
            "due_date": invoice.due_date,
            "amount": total_amount,
            "paid_amount": paid_amount,
            "adjustment_amount": adjustment_amount,
            "outstanding": outstanding,
            "payment_status": payment_status,
            "last_payment_date": payment["last_payment_date"],
        })

    paid_rows.sort(
        key=lambda row: (row["last_payment_date"] is not None, row["last_payment_date"] or date.min),
        reverse=True,
    )

    metrics["total_outstanding"] = total_outstanding
    metrics["overdue_total"] = overdue_total
    metrics["average_overdue_days"] = float(weighted_days / weighted_amount) if weighted_amount else 0
    metrics["supplier_count"] = len({row["supplier_id"] for row in report})
    metrics["open_invoice_count"] = len(report)

    return {
        "summary": totals,
        "metrics": metrics,
        "buckets": bucket_summary,
        "top_suppliers": top_suppliers,
        "details": report,
        "paid": paid_rows,
    }, invoices


@router.get("")
def get_ap_aging(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if not has_permission(current_user, "finance.view"):
        raise HTTPException(status_code=403, detail="Finance access required")
    location_id = resolve_location_id(current_user, None)
    data, _ = _aging_data(db, location_id)
    return data


@router.get("/print")
def print_ap_aging(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if not has_permission(current_user, "finance.view"):
        raise HTTPException(status_code=403, detail="Finance access required")

    today = date.today()
    location_id = resolve_location_id(current_user, None)
    data, invoices = _aging_data(db, location_id)
    supplier_rows: dict[int, dict] = {}
    bucket_keys = ("0_30", "31_60", "61_90", "91_120", "over_120")

    for invoice in invoices:
        supplier_id = invoice.supplier_id
        row = supplier_rows.setdefault(supplier_id, {
            "supplier_id": supplier_id,
            "supplier_code": getattr(invoice.supplier, "code", None) if invoice.supplier else None,
            "supplier_name": invoice.supplier.name if invoice.supplier else None,
            "purchase": ZERO,
            "payment": ZERO,
            "outstanding": ZERO,
            **{key: ZERO for key in bucket_keys},
        })
        total = Decimal(invoice.total_amount or 0)
        paid = Decimal(invoice.paid_amount or 0)
        outstanding = Decimal(invoice.balance_amount or 0)
        days = max((today - invoice.due_date).days, 0) if invoice.due_date else 0
        row["purchase"] += total
        row["payment"] += paid
        row["outstanding"] += outstanding
        row[_print_bucket(days)] += outstanding

    rows = sorted(supplier_rows.values(), key=lambda item: (item["supplier_name"] or "").upper())
    totals = {
        "purchase": sum((row["purchase"] for row in rows), ZERO),
        "payment": sum((row["payment"] for row in rows), ZERO),
        "outstanding": sum((row["outstanding"] for row in rows), ZERO),
        **{key: sum((row[key] for row in rows), ZERO) for key in bucket_keys},
    }
    return {
        "document_type": "Account Payable Aging",
        "as_of_date": today,
        "rows": rows,
        "totals": totals,
        "metrics": data["metrics"],
        **print_metadata(current_user),
    }
