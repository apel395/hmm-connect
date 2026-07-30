from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user

from app.models.chart_of_account import ChartOfAccount
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine

router = APIRouter(
    prefix="/profit-loss",
    tags=["Financial Reports"],
)


@router.get("")
def get_profit_loss(
    posting_date_from: date | None = Query(None),
    posting_date_to: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):

    query = (
        db.query(
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
        .filter(
            ChartOfAccount.account_type.in_(
                [
                    "REVENUE",
                    "EXPENSE",
                ]
            )
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
            ChartOfAccount.account_number,
            ChartOfAccount.account_name,
            ChartOfAccount.account_type,
        )
        .order_by(
            ChartOfAccount.account_number,
        )
        .all()
    )

    revenues = []
    expenses = []

    total_revenue = 0
    total_expense = 0

    for row in rows:

        if row.account_type == "REVENUE":

            amount = row.credit - row.debit

            revenues.append(
                {
                    "account_number": row.account_number,
                    "account_name": row.account_name,
                    "amount": amount,
                }
            )

            total_revenue += amount

        else:

            amount = row.debit - row.credit

            expenses.append(
                {
                    "account_number": row.account_number,
                    "account_name": row.account_name,
                    "amount": amount,
                }
            )

            total_expense += amount

    return {
        "revenues": revenues,
        "expenses": expenses,
        "total_revenue": total_revenue,
        "total_expense": total_expense,
        "net_profit": total_revenue - total_expense,
    }
