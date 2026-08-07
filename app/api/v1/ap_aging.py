from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.account_payable import AccountPayable

router = APIRouter(prefix="/ap-aging", tags=["Accounts Payable"])
ZERO = Decimal("0")
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


@router.get("")
def get_ap_aging(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    today = date.today()
    rows = db.query(AccountPayable).filter(AccountPayable.outstanding_amount > 0).all()

    totals = {key: ZERO for key in BUCKETS}
    counts = {key: 0 for key in BUCKETS}
    suppliers = {key: set() for key in BUCKETS}
    report = []
    due_today = ZERO
    overdue_total = ZERO
    overdue_count = 0
    weighted_days = ZERO
    weighted_amount = ZERO

    supplier_totals: dict[int, dict] = {}
    for ap in rows:
        outstanding = Decimal(ap.outstanding_amount or 0)
        days = (today - ap.due_date).days if ap.due_date else 0
        bucket = _bucket(days)
        values = {key: ZERO for key in BUCKETS}
        values[bucket] = outstanding
        totals[bucket] += outstanding
        counts[bucket] += 1
        suppliers[bucket].add(ap.supplier_id)
        if ap.due_date == today:
            due_today += outstanding
        if days > 0:
            overdue_total += outstanding
            overdue_count += 1
            weighted_days += outstanding * days
            weighted_amount += outstanding

        supplier = supplier_totals.setdefault(ap.supplier_id, {
            "supplier_id": ap.supplier_id,
            "supplier_name": ap.supplier.name if ap.supplier else None,
            "outstanding": ZERO,
            "invoice_count": 0,
            "overdue": ZERO,
        })
        supplier["outstanding"] += outstanding
        supplier["invoice_count"] += 1
        if days > 0:
            supplier["overdue"] += outstanding

        report.append({
            "id": ap.id,
            "invoice_number": ap.invoice_number,
            "supplier_id": ap.supplier_id,
            "supplier_name": ap.supplier.name if ap.supplier else None,
            "invoice_date": ap.invoice_date,
            "due_date": ap.due_date,
            "amount": ap.amount,
            "paid_amount": ap.paid_amount,
            "outstanding": outstanding,
            "payment_status": ap.payment_status,
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

    paid = db.query(AccountPayable).filter(AccountPayable.paid_amount > 0).order_by(AccountPayable.last_payment_date.desc().nullslast(), AccountPayable.id.desc()).all()
    paid_rows = [{
        "id": ap.id,
        "invoice_number": ap.invoice_number,
        "supplier_id": ap.supplier_id,
        "supplier_name": ap.supplier.name if ap.supplier else None,
        "invoice_date": ap.invoice_date,
        "due_date": ap.due_date,
        "amount": ap.amount,
        "paid_amount": ap.paid_amount,
        "outstanding": ap.outstanding_amount,
        "payment_status": ap.payment_status,
        "last_payment_date": ap.last_payment_date,
    } for ap in paid]

    return {
        "summary": totals,
        "metrics": {
            "total_outstanding": total_outstanding,
            "due_today": due_today,
            "overdue_total": overdue_total,
            "overdue_invoice_count": overdue_count,
            "open_invoice_count": len(rows),
            "supplier_count": len({row.supplier_id for row in rows}),
            "average_overdue_days": float(weighted_days / weighted_amount) if weighted_amount else 0,
        },
        "buckets": bucket_summary,
        "top_suppliers": top_suppliers,
        "details": report,
        "paid": paid_rows,
    }
