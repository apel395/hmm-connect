from datetime import date
from decimal import Decimal

from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session, contains_eager, joinedload

from app.models.chart_of_account import ChartOfAccount
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.supplier import Supplier

ZERO = Decimal("0")


def build_ledger_query(
    db: Session,
    *,
    account_id: int | None = None,
    account_from_id: int | None = None,
    account_to_id: int | None = None,
    search_type: str = "ALL",
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
    if account_from_id:
        start = db.get(ChartOfAccount, account_from_id)
        if start:
            q = q.filter(JournalLine.account.has(ChartOfAccount.account_number >= start.account_number))
    if account_to_id:
        end = db.get(ChartOfAccount, account_to_id)
        if end:
            q = q.filter(JournalLine.account.has(ChartOfAccount.account_number <= end.account_number))
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
        choices = {
            "JOURNAL": JournalEntry.journal_number.ilike(term),
            "DOCUMENT": JournalEntry.document_number.ilike(term),
            "DESCRIPTION": JournalLine.description.ilike(term),
            "ACCOUNT": JournalLine.account.has(or_(ChartOfAccount.account_number.ilike(term), ChartOfAccount.account_name.ilike(term))),
            "SUPPLIER": JournalLine.supplier.has(or_(Supplier.name.ilike(term), Supplier.code.ilike(term))),
        }
        if search_type.upper() == "ALL":
            q = q.filter(or_(*choices.values()))
        elif search_type.upper() in choices:
            q = q.filter(choices[search_type.upper()])
        else:
            raise ValueError("Unsupported ledger search type")
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


def _signed_delta():
    """Signed line movement where a positive number increases the account balance."""
    debit_delta = func.coalesce(JournalLine.debit, 0) - func.coalesce(JournalLine.credit, 0)
    credit_delta = func.coalesce(JournalLine.credit, 0) - func.coalesce(JournalLine.debit, 0)
    return case((ChartOfAccount.normal_balance == "DEBIT", debit_delta), else_=credit_delta)


def opening_balances(
    db: Session,
    *,
    account_id: int | None = None,
    account_from_id: int | None = None,
    account_to_id: int | None = None,
    date_from: date | None = None,
    reference_type: str | None = None,
    supplier_id: int | None = None,
    department_id: int | None = None,
    location_id: int | None = None,
    business_unit_id: int | None = None,
) -> dict[int, Decimal]:
    """Per-account balance carried into the period (everything before date_from).

    The text search is intentionally ignored so a display-only filter does not
    break the opening -> movement -> closing chain. All other movement filters
    are honoured so the closing balance stays consistent with what is printed.
    """
    if not date_from:
        return {}
    q = build_ledger_query(
        db,
        account_id=account_id,
        account_from_id=account_from_id,
        account_to_id=account_to_id,
        reference_type=reference_type,
        supplier_id=supplier_id,
        department_id=department_id,
        location_id=location_id,
        business_unit_id=business_unit_id,
    )
    rows = (
        q.filter(JournalEntry.posting_date < date_from)
        .join(ChartOfAccount, ChartOfAccount.id == JournalLine.account_id)
        .with_entities(JournalLine.account_id, func.coalesce(func.sum(_signed_delta()), 0))
        .group_by(JournalLine.account_id)
        .all()
    )
    return {account_id_value: Decimal(total) for account_id_value, total in rows}


def ledger_report_rows(q):
    return (
        q.join(ChartOfAccount, ChartOfAccount.id == JournalLine.account_id)
        .options(
            contains_eager(JournalLine.journal_entry),
            joinedload(JournalLine.account),
            joinedload(JournalLine.department),
            joinedload(JournalLine.location),
            joinedload(JournalLine.business_unit),
            joinedload(JournalLine.supplier),
        )
        .order_by(
            JournalLine.account_id,
            JournalEntry.posting_date,
            JournalEntry.id,
            JournalLine.line_number,
            JournalLine.id,
        )
    )


def _report_row(line, balance: Decimal) -> dict:
    entry = line.journal_entry
    return {
        "id": line.id,
        "posting_date": entry.posting_date,
        "journal_id": entry.id,
        "journal_number": entry.journal_number,
        "document_type": entry.document_type,
        "document_number": entry.document_number,
        "reference": entry.external_reference,
        "description": line.description,
        "supplier_name": line.supplier.name if line.supplier else None,
        "department_name": line.department.name if line.department else None,
        "location_name": line.location.name if line.location else None,
        "business_unit_name": line.business_unit.name if line.business_unit else None,
        "debit": line.debit,
        "credit": line.credit,
        "balance": balance,
    }


def _account_metadata(account: ChartOfAccount) -> dict:
    return {
        "account_id": account.id,
        "account_code": account.account_number,
        "account_name": account.account_name,
        "account_type": account.account_type,
        "normal_balance": account.normal_balance,
    }


def ledger_grouped_report(
    db: Session,
    *,
    account_id: int | None = None,
    account_from_id: int | None = None,
    account_to_id: int | None = None,
    search_type: str = "ALL",
    date_from: date | None = None,
    date_to: date | None = None,
    reference_type: str | None = None,
    supplier_id: int | None = None,
    department_id: int | None = None,
    location_id: int | None = None,
    business_unit_id: int | None = None,
    search: str | None = None,
) -> tuple[list[dict], Decimal, Decimal]:
    """Audit-ready ledger grouped by account with opening/activity/closing blocks."""
    q = build_ledger_query(
        db,
        account_id=account_id,
        account_from_id=account_from_id,
        account_to_id=account_to_id,
        search_type=search_type,
        date_from=date_from,
        date_to=date_to,
        reference_type=reference_type,
        supplier_id=supplier_id,
        department_id=department_id,
        location_id=location_id,
        business_unit_id=business_unit_id,
        search=search,
    )
    openings = opening_balances(
        db,
        account_id=account_id,
        account_from_id=account_from_id,
        account_to_id=account_to_id,
        date_from=date_from,
        reference_type=reference_type,
        supplier_id=supplier_id,
        department_id=department_id,
        location_id=location_id,
        business_unit_id=business_unit_id,
    )

    groups: dict[int, dict] = {}
    for line in ledger_report_rows(q).all():
        account = line.account
        group = groups.get(account.id)
        if group is None:
            opening = openings.get(account.id, ZERO)
            group = {
                **_account_metadata(account),
                "opening_balance": opening,
                "running_balance": opening,
                "total_debit": ZERO,
                "total_credit": ZERO,
                "rows": [],
            }
            groups[account.id] = group
        debit = Decimal(line.debit or 0)
        credit = Decimal(line.credit or 0)
        delta = (debit - credit) if account.normal_balance == "DEBIT" else (credit - debit)
        group["running_balance"] += delta
        group["total_debit"] += debit
        group["total_credit"] += credit
        group["rows"].append(_report_row(line, group["running_balance"]))

    # Accounts that had prior activity but no rows in the period still need a block.
    for account_id_value, opening in openings.items():
        if account_id_value in groups or opening == ZERO:
            continue
        account = db.get(ChartOfAccount, account_id_value)
        if not account:
            continue
        groups[account_id_value] = {
            **_account_metadata(account),
            "opening_balance": opening,
            "running_balance": opening,
            "total_debit": ZERO,
            "total_credit": ZERO,
            "rows": [],
        }

    # When a single account is requested, always show its block even if empty.
    if account_id and account_id not in groups:
        account = db.get(ChartOfAccount, account_id)
        if account:
            groups[account_id] = {
                **_account_metadata(account),
                "opening_balance": ZERO,
                "running_balance": ZERO,
                "total_debit": ZERO,
                "total_credit": ZERO,
                "rows": [],
            }

    accounts = sorted(groups.values(), key=lambda group: group["account_code"])
    for group in accounts:
        group["closing_balance"] = group["running_balance"]

    control_debit = sum((group["total_debit"] for group in accounts), ZERO)
    control_credit = sum((group["total_credit"] for group in accounts), ZERO)
    return accounts, control_debit, control_credit