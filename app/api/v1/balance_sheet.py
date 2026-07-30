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
    prefix="/balance-sheet",
    tags=["Financial Reports"],
)


@router.get("")
def get_balance_sheet(
    posting_date: date | None = Query(None),
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
    )

    if posting_date:
        query = query.filter(
            JournalEntry.posting_date <= posting_date
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

    assets = []
    liabilities = []
    equity = []

    total_assets = 0
    total_liabilities = 0
    total_equity = 0

    for row in rows:

        balance = row.debit - row.credit

        data = {
            "account_number": row.account_number,
            "account_name": row.account_name,
            "balance": balance,
        }

        if row.account_type == "ASSET":
            assets.append(data)
            total_assets += balance

        elif row.account_type == "LIABILITY":
            liabilities.append(data)
            total_liabilities += -balance

        elif row.account_type == "EQUITY":
            equity.append(data)
            total_equity += -balance

    return {
        "assets": assets,
        "liabilities": liabilities,
        "equity": equity,
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "total_equity": total_equity,
        "balanced": total_assets == (total_liabilities + total_equity),
    }
