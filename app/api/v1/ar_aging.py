from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user

from app.models.account_receivable import AccountReceivable

router = APIRouter(
    prefix="/ar-aging",
    tags=["Accounts Receivable"],
)


@router.get("")
def get_ar_aging(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):

    today = date.today()

    rows = (
        db.query(AccountReceivable)
        .filter(
            AccountReceivable.outstanding_amount > 0
        )
        .all()
    )

    report = []

    total_current = 0
    total_30 = 0
    total_60 = 0
    total_90 = 0
    total_over_90 = 0

    for ar in rows:

        days = (today - ar.due_date).days

        current = 0
        bucket30 = 0
        bucket60 = 0
        bucket90 = 0
        bucket_over90 = 0

        if days <= 0:

            current = ar.outstanding_amount
            total_current += current

        elif days <= 30:

            bucket30 = ar.outstanding_amount
            total_30 += bucket30

        elif days <= 60:

            bucket60 = ar.outstanding_amount
            total_60 += bucket60

        elif days <= 90:

            bucket90 = ar.outstanding_amount
            total_90 += bucket90

        else:

            bucket_over90 = ar.outstanding_amount
            total_over_90 += bucket_over90

        report.append(
            {
                "invoice_number": ar.invoice_number,
                "customer_id": ar.customer_id,
                "due_date": ar.due_date,
                "outstanding": ar.outstanding_amount,
                "current": current,
                "1_30": bucket30,
                "31_60": bucket60,
                "61_90": bucket90,
                "over_90": bucket_over90,
            }
        )

    return {
        "summary": {
            "current": total_current,
            "1_30": total_30,
            "31_60": total_60,
            "61_90": total_90,
            "over_90": total_over_90,
        },
        "details": report,
    }
