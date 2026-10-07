from datetime import date
from decimal import Decimal
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_permission
from app.models.business_unit import BusinessUnit
from app.models.chart_of_account import ChartOfAccount
from app.models.department import Department
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.location import Location
from app.services.document_context import print_metadata
from app.services.general_ledger_report import (
    build_ledger_query,
    ledger_grouped_report,
    opening_balances,
    ledger_rows_with_balance,
    ledger_totals,
    serialize_ledger_item,
)
from app.services.location_access import resolve_location_id

router = APIRouter(prefix="/general-ledger", tags=["General Ledger"])
ZERO = Decimal("0")


def access(user):
    if not has_permission(user, "journal.view"):
        raise HTTPException(403, "Finance access required")


def _search_pattern(search: str | None) -> str | None:
    token = str(search or "").strip()
    return f"%{token}%" if token else None


def _item(line, balance):
    return serialize_ledger_item(line, balance)


def _dimension_name(db: Session, model, value: int | None) -> str | None:
    if not value:
        return None
    entity = db.get(model, value)
    return entity.name if entity else None


@router.get("")
def listing(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    search_type: str = Query("ALL", pattern="^(ALL|JOURNAL|DOCUMENT|DESCRIPTION|ACCOUNT|SUPPLIER)$"),
    account_id: int | None = None,
    account_ids: str | None = None,
    account_from_id: int | None = None,
    account_to_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    reference_type: str | None = None,
    supplier_id: int | None = None,
    department_id: int | None = None,
    location_id: int | None = None,
    business_unit_id: int | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    access(user)
    location_id = resolve_location_id(user, location_id)
    if account_id and (account_from_id or account_to_id):
        raise HTTPException(422, "Choose a single account or an account range")
    start = db.get(ChartOfAccount, account_from_id) if account_from_id else None
    end = db.get(ChartOfAccount, account_to_id) if account_to_id else None
    if (account_from_id and not start) or (account_to_id and not end):
        raise HTTPException(404, "Account range endpoint not found")
    if start and end and start.account_number > end.account_number:
        raise HTTPException(422, "From Account must not be after To Account")
    q = build_ledger_query(
        db,
        account_id=account_id,
        account_ids=account_ids,
        account_from_id=account_from_id,
        account_to_id=account_to_id,
        search_type=search_type,
        date_from=date_from,
        date_to=date_to,
        reference_type=reference_type,
        supplier_id=supplier_id,
        department_id=department_id,
        location_id=location_id,
        search=search,
        business_unit_id=business_unit_id,
    )
    total = q.count()
    total_debit, total_credit = ledger_totals(q)
    rows = ledger_rows_with_balance(q).offset((page - 1) * page_size).limit(page_size).all()
    openings = opening_balances(
        db, account_id=account_id, account_ids=account_ids, account_from_id=account_from_id,
        account_to_id=account_to_id, date_from=date_from,
        reference_type=reference_type, supplier_id=supplier_id,
        department_id=department_id, location_id=location_id,
        business_unit_id=business_unit_id,
    )
    return {
        "items": [_item(line, Decimal(balance or 0) + openings.get(line.account_id, ZERO)) for line, balance in rows],
        "summary": {"total_debit": total_debit, "total_credit": total_credit, "difference": total_debit - total_credit},
        "page": page,
        "page_size": page_size,
        "total_items": total,
        "total_pages": ceil(total / page_size) if total else 0,
        "has_next": page * page_size < total,
        "has_previous": page > 1,
    }


@router.get("/print")
def printable(
    search: str | None = None,
    search_type: str = Query("ALL", pattern="^(ALL|JOURNAL|DOCUMENT|DESCRIPTION|ACCOUNT|SUPPLIER)$"),
    account_id: int | None = None,
    account_ids: str | None = None,
    account_from_id: int | None = None,
    account_to_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    reference_type: str | None = None,
    supplier_id: int | None = None,
    department_id: int | None = None,
    location_id: int | None = None,
    business_unit_id: int | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    access(user)
    location_id = resolve_location_id(user, location_id)
    if account_id and (account_from_id or account_to_id):
        raise HTTPException(422, "Choose a single account or an account range")
    start = db.get(ChartOfAccount, account_from_id) if account_from_id else None
    end = db.get(ChartOfAccount, account_to_id) if account_to_id else None
    if (account_from_id and not start) or (account_to_id and not end):
        raise HTTPException(404, "Account range endpoint not found")
    if start and end and start.account_number > end.account_number:
        raise HTTPException(422, "From Account must not be after To Account")
    accounts, control_debit, control_credit = ledger_grouped_report(
        db,
        account_id=account_id,
        account_ids=account_ids,
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
    account = db.get(ChartOfAccount, account_id) if account_id else None
    return {
        "document_type": "General Ledger",
        "period": {"date_from": date_from, "date_to": date_to},
        "filters": {
            "account_id": account_id,
            "account_ids": account_ids,
            "account_from_id": account_from_id,
            "account_to_id": account_to_id,
            "search_type": search_type,
            "account_code": account.account_number if account else None,
            "account_name": account.account_name if account else None,
            "business_unit_id": business_unit_id,
            "business_unit_name": _dimension_name(db, BusinessUnit, business_unit_id),
            "location_id": location_id,
            "location_name": _dimension_name(db, Location, location_id),
            "department_id": department_id,
            "department_name": _dimension_name(db, Department, department_id),
            "reference_type": reference_type,
            "supplier_id": supplier_id,
            "search": search,
        },
        "accounts": accounts,
        "control": {
            "total_debit": control_debit,
            "total_credit": control_credit,
            "difference": control_debit - control_credit,
        },
        **print_metadata(user),
    }


@router.get("/accounts/{account_id}/summary")
def summary(account_id: int, date_from: date | None = None, date_to: date | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    account = db.get(ChartOfAccount, account_id)
    if not account:
        raise HTTPException(404, "Account not found")
    location_id = resolve_location_id(user, None)
    opening = opening_balances(
        db, account_id=account_id, date_from=date_from, location_id=location_id,
    ).get(account_id, ZERO)
    q = build_ledger_query(db, account_id=account_id, date_from=date_from, date_to=date_to, location_id=location_id)
    td, tc = q.with_entities(func.coalesce(func.sum(JournalLine.debit), 0), func.coalesce(func.sum(JournalLine.credit), 0)).one()
    movement = Decimal(td) - Decimal(tc) if account.normal_balance == "DEBIT" else Decimal(tc) - Decimal(td)
    return {"account_id": account.id, "account_code": account.account_number, "account_name": account.account_name, "normal_balance": account.normal_balance, "opening_balance": opening, "total_debit": td, "total_credit": tc, "closing_balance": opening + movement}
