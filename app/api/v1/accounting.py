from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user

from app.models.chart_of_account import ChartOfAccount
from app.models.general_ledger import GeneralLedger

router = APIRouter(
    prefix="/accounting",
    tags=["Accounting"],
)


@router.get("/trial-balance")
def trial_balance(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):

    rows = (
        db.query(
            ChartOfAccount.id,
            ChartOfAccount.account_number,
            ChartOfAccount.account_name,
            func.coalesce(func.sum(GeneralLedger.debit), 0).label("debit"),
            func.coalesce(func.sum(GeneralLedger.credit), 0).label("credit"),
        )
        .outerjoin(
            GeneralLedger,
            GeneralLedger.account_id == ChartOfAccount.id,
        )
        .group_by(
            ChartOfAccount.id,
            ChartOfAccount.account_number,
            ChartOfAccount.account_name,
        )
        .order_by(
            ChartOfAccount.account_number,
        )
        .all()
    )

    result = []

    total_debit = Decimal("0")
    total_credit = Decimal("0")

    for row in rows:

        balance = Decimal(row.debit) - Decimal(row.credit)

        result.append(
            {
                "account_id": row.id,
                "account_number": row.account_number,
                "account_name": row.account_name,
                "debit": row.debit,
                "credit": row.credit,
                "balance": balance,
            }
        )

        total_debit += Decimal(row.debit)
        total_credit += Decimal(row.credit)

    return {
        "accounts": result,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "balanced": total_debit == total_credit,
    }

@router.get("/general-ledger")
def general_ledger(
    account_id: int | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):

    query = db.query(GeneralLedger)

    if account_id:
        query = query.filter(
            GeneralLedger.account_id == account_id
        )

    entries = (
        query.order_by(
            GeneralLedger.posting_date,
            GeneralLedger.id,
        )
        .all()
    )

    return entries

@router.get("/account-ledger/{account_id}")
def account_ledger(
    account_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):

    entries = (
        db.query(GeneralLedger)
        .filter(
            GeneralLedger.account_id == account_id
        )
        .order_by(
            GeneralLedger.posting_date,
            GeneralLedger.id,
        )
        .all()
    )

    running = Decimal("0")

    result = []

    for e in entries:

        running += Decimal(e.debit)
        running -= Decimal(e.credit)

        result.append(
            {
                "date": e.posting_date,
                "description": e.description,
                "debit": e.debit,
                "credit": e.credit,
                "balance": running,
                "reference": e.reference_number,
            }
        )

    return result
