from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_any_role
from app.models.payment import Payment, PaymentAllocation
from app.models.supplier_invoice import SupplierInvoice
from app.services.ap_metrics import OPEN_AP_STATUSES, ZERO, ap_metrics, open_invoice_query

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


def _last_payment_dates(db: Session) -> dict[int, date]:
    rows = (
        db.query(
            PaymentAllocation.supplier_invoice_id,
            func.max(Payment.payment_date),
        )
        .join(Payment, Payment.id == PaymentAllocation.payment_id)
        .filter(Payment.status == "POSTED")
        .group_by(PaymentAllocation.supplier_invoice_id)
        .all()
    )
    return {invoice_id: payment_date for invoice_id, payment_date in rows}


@router.get("")
def get_ap_aging(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if not has_any_role(current_user, "FINANCE", "AUDITOR"):
        raise HTTPException(status_code=403, detail="Finance access required")

    today = date.today()
    metrics, invoices = ap_metrics(db, as_of_date=today)
    last_payment_dates = _last_payment_dates(db)

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
        .filter(
            SupplierInvoice.status.in_(OPEN_AP_STATUSES),
            SupplierInvoice.paid_amount > 0,
        )
        .order_by(SupplierInvoice.id.desc())
        .all()
    )
    paid_rows = [{
        "id": invoice.id,
        "supplier_invoice_id": invoice.id,
        "invoice_number": invoice.internal_invoice_number,
        "supplier_invoice_number": invoice.supplier_invoice_number,
        "supplier_id": invoice.supplier_id,
        "supplier_name": invoice.supplier.name if invoice.supplier else None,
        "invoice_date": invoice.invoice_date,
        "due_date": invoice.due_date,
        "amount": invoice.total_amount,
        "paid_amount": invoice.paid_amount,
        "adjustment_amount": invoice.adjustment_amount,
        "outstanding": invoice.balance_amount,
        "payment_status": invoice.payment_status,
        "last_payment_date": last_payment_dates.get(invoice.id),
    } for invoice in paid_invoices]
    paid_rows.sort(key=lambda row: (row["last_payment_date"] is not None, row["last_payment_date"] or date.min), reverse=True)

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
    }
