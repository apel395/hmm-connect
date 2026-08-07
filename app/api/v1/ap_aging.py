from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.account_payable import AccountPayable

router = APIRouter(prefix="/ap-aging", tags=["Accounts Payable"])


@router.get("")
def get_ap_aging(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    today = date.today()
    rows = db.query(AccountPayable).filter(AccountPayable.outstanding_amount > 0).all()

    report = []
    totals = {"current": 0, "1_30": 0, "31_60": 0, "61_90": 0, "over_90": 0}
    for ap in rows:
        days = (today - ap.due_date).days if ap.due_date else 0
        bucket = "current" if days <= 0 else "1_30" if days <= 30 else "31_60" if days <= 60 else "61_90" if days <= 90 else "over_90"
        values = {key: 0 for key in totals}
        values[bucket] = ap.outstanding_amount
        totals[bucket] += ap.outstanding_amount
        report.append({
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
            **values,
        })

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

    return {"summary": totals, "details": report, "paid": paid_rows}
