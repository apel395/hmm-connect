from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user

from app.models.chart_of_account import ChartOfAccount
from app.models.journal_line import JournalLine
from app.models.journal_entry import JournalEntry

router = APIRouter(
    prefix="/trial-balance",
    tags=["Financial Reports"],
)


@router.get("")
def get_trial_balance(
    posting_date_from: date | None = Query(None),
    posting_date_to: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):

    query = (
        db.query(
            ChartOfAccount.id,
            ChartOfAccount.account_number,
            ChartOfAccount.account_name,
            ChartOfAccount.account_type,
            func.coalesce(func.sum(JournalLine.debit), 0).label("debit"),
            func.coalesce(func.sum(JournalLine.credit), 0).label("credit"),
        )
        .join(
            JournalLine,
            JournalLine.account_id == ChartOfAccount.id,
        )
        .join(
            JournalEntry,
            JournalEntry.id == JournalLine.journal_entry_id,
        )
    )

    if posting_date_from:
        query = query.filter(
            JournalEntry.posting_date >= posting_date_from
        )

    if posting_date_to:
        query = query.filter(
            JournalEntry.posting_date <= posting_date_to
        )

    rows = (
        query.group_by(
            ChartOfAccount.id,
            ChartOfAccount.account_number,
            ChartOfAccount.account_name,
            ChartOfAccount.account_type,
        )
        .order_by(
            ChartOfAccount.account_number,
        )
        .all()
    )

    total_debit = sum(r.debit for r in rows)
    total_credit = sum(r.credit for r in rows)

    return {
        "total_debit": total_debit,
        "total_credit": total_credit,
        "balanced": total_debit == total_credit,
        "accounts": rows,
    }
