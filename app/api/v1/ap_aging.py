from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_any_role
from app.models.payment import Payment, PaymentAllocation
from app.models.supplier_invoice import SupplierInvoice

router = APIRouter(prefix="/ap-aging", tags=["Accounts Payable"])
ZERO = Decimal("0")
BUCKETS = ("current", "1_30", "31_60", "61_90", "over_90")
OPEN_INVOICE_STATUSES = {"VERIFIED", "POSTED"}


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


def _payment_totals(db: Session) -> dict[int, dict]:
    rows = (
        db.query(
            PaymentAllocation.supplier_invoice_id,
            func.coalesce(func.sum(PaymentAllocation.allocated_amount), 0),
            func.max(Payment.payment_date),
        )
        .join(Payment, Payment.id == PaymentAllocation.payment_id)
        .filter(Payment.status == "POSTED")
        .group_by(PaymentAllocation.supplier_invoice_id)
        .all()
    )
    return {
        invoice_id: {"paid_amount": Decimal(paid_amount or 0), "last_payment_date": last_payment_date}
        for invoice_id, paid_amount, last_payment_date in rows
    }


@router.get("")
def get_ap_aging(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if not has_any_role(current_user, "FINANCE", "AUDITOR"):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Finance access required")

    today = date.today()
    payment_totals = _payment_totals(db)
    invoices = (
        db.query(SupplierInvoice)
        .filter(SupplierInvoice.status.in_(OPEN_INVOICE_STATUSES), SupplierInvoice.total_amount > 0)
        .order_by(SupplierInvoice.due_date.asc().nullslast(), SupplierInvoice.id.asc())
        .all()
    )

    totals = {key: ZERO for key in BUCKETS}
    counts = {key: 0 for key in BUCKETS}
    suppliers = {key: set() for key in BUCKETS}
    report = []
    paid_rows = []
    due_today = ZERO
    overdue_total = ZERO
    overdue_count = 0
    weighted_days = ZERO
    weighted_amount = ZERO
    supplier_totals: dict[int, dict] = {}

    for invoice in invoices:
        payment = payment_totals.get(invoice.id, {})
        paid_amount = Decimal(payment.get("paid_amount", 0))
        total_amount = Decimal(invoice.total_amount or 0)
        outstanding = max(ZERO, total_amount - paid_amount)
        payment_status = "PAID" if outstanding == 0 else "PARTIALLY_PAID" if paid_amount > 0 else "UNPAID"

        if paid_amount > 0:
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
                "outstanding": outstanding,
                "payment_status": payment_status,
                "last_payment_date": payment.get("last_payment_date"),
            })

        if outstanding <= 0:
            continue

        days = (today - invoice.due_date).days if invoice.due_date else 0
        bucket = _bucket(days)
        values = {key: ZERO for key in BUCKETS}
        values[bucket] = outstanding
        totals[bucket] += outstanding
        counts[bucket] += 1
        suppliers[bucket].add(invoice.supplier_id)
        if invoice.due_date == today:
            due_today += outstanding
        if days > 0:
            overdue_total += outstanding
            overdue_count += 1
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
            "outstanding": outstanding,
            "payment_status": payment_status,
            "days_overdue": max(days, 0),
            "aging_bucket": bucket,
            **values,
        })

    total_outstanding = sum(totals.values(), ZERO)
    bucket_summary = {key: {
        "amount": totals[key],
        "invoice_count": counts[key],
        "supplier_count": len(suppliers[key]),
        "percentage": float((totals[key] / total_outstanding * 100) if total_outstanding else ZERO),
    } for key in BUCKETS}
    top_suppliers = sorted(supplier_totals.values(), key=lambda row: row["outstanding"], reverse=True)[:10]
    paid_rows.sort(key=lambda row: (row["last_payment_date"] is not None, row["last_payment_date"] or date.min), reverse=True)

    return {
        "summary": totals,
        "metrics": {
            "total_outstanding": total_outstanding,
            "due_today": due_today,
            "overdue_total": overdue_total,
            "overdue_invoice_count": overdue_count,
            "open_invoice_count": len(report),
            "supplier_count": len({row["supplier_id"] for row in report}),
            "average_overdue_days": float(weighted_days / weighted_amount) if weighted_amount else 0,
        },
        "buckets": bucket_summary,
        "top_suppliers": top_suppliers,
        "details": report,
        "paid": paid_rows,
    }
