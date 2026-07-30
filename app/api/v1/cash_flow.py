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
    prefix="/cash-flow",
    tags=["Financial Reports"],
)


@router.get("")
def cash_flow(
    posting_date_from: date | None = Query(None),
    posting_date_to: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):

    query = (
        db.query(
            ChartOfAccount.cash_flow_category,
            ChartOfAccount.account_number,
            ChartOfAccount.account_name,
            func.sum(JournalLine.debit).label("debit"),
            func.sum(JournalLine.credit).label("credit"),
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
            ChartOfAccount.cash_flow_category.is_not(None)
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
            ChartOfAccount.cash_flow_category,
            ChartOfAccount.account_number,
            ChartOfAccount.account_name,
        )
        .order_by(
            ChartOfAccount.account_number,
        )
        .all()
    )

    operating = []
    investing = []
    financing = []

    total_operating = 0
    total_investing = 0
    total_financing = 0

    for row in rows:

        amount = float(row.debit or 0) - float(row.credit or 0)

        item = {
            "account_number": row.account_number,
            "account_name": row.account_name,
            "amount": amount,
        }

        if row.cash_flow_category == "OPERATING":

            operating.append(item)
            total_operating += amount

        elif row.cash_flow_category == "INVESTING":

            investing.append(item)
            total_investing += amount

        elif row.cash_flow_category == "FINANCING":

            financing.append(item)
            total_financing += amount

    return {
        "operating": operating,
        "investing": investing,
        "financing": financing,
        "net_cash_flow": (
            total_operating
            + total_investing
            + total_financing
        ),
    }
