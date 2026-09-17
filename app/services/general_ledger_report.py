from datetime import date
from decimal import Decimal

from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from app.models.chart_of_account import ChartOfAccount
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine

ZERO = Decimal("0")


def build_ledger_query(
    db: Session,
    *,
    account_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    reference_type: str | None = None,
    supplier_id: int | None = None,
    department_id: int | None = None,
    location_id: int | None = None,
    business_unit_id: int | None = None,
    search: str | None = None,
):
    q = db.query(JournalLine).join(JournalEntry).filter(JournalEntry.status == "POSTED")
    if account_id:
        q = q.filter(JournalLine.account_id == account_id)
    if date_from:
        q = q.filter(JournalEntry.posting_date >= date_from)
    if date_to:
        q = q.filter(JournalEntry.posting_date <= date_to)
    if reference_type:
        q = q.filter(JournalEntry.reference_type == reference_type)
    if supplier_id:
        q = q.filter(JournalLine.supplier_id == supplier_id)
    if department_id:
        q = q.filter(JournalLine.department_id == department_id)
    if location_id:
        q = q.filter(JournalLine.location_id == location_id)
    if business_unit_id:
        q = q.filter(JournalLine.business_unit_id == business_unit_id)
    token = str(search or "").strip()
    term = f"%{token}%" if token else None
    if term:
        q = q.filter(or_(
            JournalEntry.journal_number.ilike(term),
            JournalEntry.document_number.ilike(term),
            JournalLine.description.ilike(term),
        ))
    return q


def ledger_rows_with_balance(q):
    debit_normal_delta = func.coalesce(JournalLine.debit, 0) - func.coalesce(JournalLine.credit, 0)
    credit_normal_delta = func.coalesce(JournalLine.credit, 0) - func.coalesce(JournalLine.debit, 0)
    delta = case((ChartOfAccount.normal_balance == "DEBIT", debit_normal_delta), else_=credit_normal_delta)
    running_balance = func.sum(delta).over(
        partition_by=JournalLine.account_id,
        order_by=(JournalEntry.posting_date, JournalEntry.id, JournalLine.line_number, JournalLine.id),
        rows=(None, 0),
    ).label("running_balance")
    return (
        q.join(ChartOfAccount, ChartOfAccount.id == JournalLine.account_id)
        .with_entities(JournalLine, running_balance)
        .order_by(JournalEntry.posting_date, JournalEntry.id, JournalLine.line_number, JournalLine.id)
    )


def ledger_totals(q):
    total_debit, total_credit = q.with_entities(
        func.coalesce(func.sum(JournalLine.debit), 0),
        func.coalesce(func.sum(JournalLine.credit), 0),
    ).one()
    return Decimal(total_debit), Decimal(total_credit)


def serialize_ledger_item(line, balance: Decimal | None) -> dict:
    account = line.account
    return {
        "id": line.id,
        "posting_date": line.journal_entry.posting_date,
        "journal_id": line.journal_entry.id,
        "journal_number": line.journal_entry.journal_number,
        "account_id": account.id,
        "account_code": account.account_number,
        "account_name": account.account_name,
        "description": line.description,
        "reference_type": line.journal_entry.reference_type,
        "reference_number": line.journal_entry.document_number,
        "debit": line.debit,
        "credit": line.credit,
        "balance": balance or ZERO,
        "supplier_id": line.supplier_id,
        "supplier_name": line.supplier.name if line.supplier else None,
        "department_id": line.department_id,
        "department_name": line.department.name if line.department else None,
        "location_id": line.location_id,
        "location_name": line.location.name if line.location else None,
        "business_unit_id": line.business_unit_id,
        "business_unit_name": line.business_unit.name if line.business_unit else None,
    }