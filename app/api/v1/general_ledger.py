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
from app.models.location import Location
from app.services.document_context import print_metadata
from app.services.general_ledger_report import (
    build_ledger_query,
    ledger_grouped_report,
    ledger_rows_with_balance,
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
    account_id: int | None = None,
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
    q = build_ledger_query(
        db,
        account_id=account_id,
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
    rows = ledger_rows_with_balance(q).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [_item(line, balance) for line, balance in rows],
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
    account_id: int | None = None,
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
    accounts, control_debit, control_credit = ledger_grouped_report(
        db,
        account_id=account_id,
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
    opening_q = build_ledger_query(db, account_id=account_id, date_to=date_from, location_id=location_id)
    if date_from:
        opening_q = opening_q.filter(JournalEntry.posting_date < date_from)
    else:
        opening_q = opening_q.filter(False)
    od, oc = opening_q.with_entities(func.coalesce(func.sum(JournalLine.debit), 0), func.coalesce(func.sum(JournalLine.credit), 0)).one()
    q = build_ledger_query(db, account_id=account_id, date_from=date_from, date_to=date_to, location_id=location_id)
    td, tc = q.with_entities(func.coalesce(func.sum(JournalLine.debit), 0), func.coalesce(func.sum(JournalLine.credit), 0)).one()
    opening = Decimal(od) - Decimal(oc) if account.normal_balance == "DEBIT" else Decimal(oc) - Decimal(od)
    movement = Decimal(td) - Decimal(tc) if account.normal_balance == "DEBIT" else Decimal(tc) - Decimal(td)
    return {"account_id": account.id, "account_code": account.account_number, "account_name": account.account_name, "normal_balance": account.normal_balance, "opening_balance": opening, "total_debit": td, "total_credit": tc, "closing_balance": opening + movement}