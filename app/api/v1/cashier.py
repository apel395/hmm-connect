"""Cashier draft and posting flows backed by the existing journal ledger."""
from datetime import date
from decimal import Decimal
from math import ceil
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.authorization import require_permission
from app.models.chart_of_account import ChartOfAccount
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.services.audit import record_audit
from app.services.document_number import next_document_number
from app.services.location_access import resolve_location_id, enforce_location_access
from app.services.organization_dimensions import validate_dimensions
from app.api.v1.journals import post_locked_journal, serialize

router = APIRouter(prefix="/cashier", tags=["General Cashier"])
view = require_permission("finance.view")
manage = require_permission("finance.manage")
CASH = {"BANK", "CASH", "PETTY_CASH"}
SOURCE = "GENERAL_CASHIER"


class CashEntry(BaseModel):
    posting_date: date
    operation: Literal["RECEIPT", "PAYMENT", "TRANSFER"]
    cash_account_id: int
    counterpart_account_id: int
    amount: Decimal = Field(gt=0, decimal_places=2)
    location_id: int
    business_unit_id: int | None = None
    department_id: int | None = None
    reference_number: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=500)


def validate_accounts(db, data):
    cash = db.get(ChartOfAccount, data.cash_account_id)
    other = db.get(ChartOfAccount, data.counterpart_account_id)
    for account in (cash, other):
        if not account or not account.is_active or not account.is_posting:
            raise HTTPException(422, "Select active posting accounts")
    if cash.id == other.id:
        raise HTTPException(422, "Cash and counterpart accounts must differ")
    if cash.account_type != "ASSET" or cash.account_subtype not in CASH:
        raise HTTPException(422, "Select a cash, bank or petty-cash account")
    if data.operation == "TRANSFER":
        if other.account_type != "ASSET" or other.account_subtype not in CASH:
            raise HTTPException(422, "Transfers require two cash/bank accounts")
    elif data.operation == "PAYMENT":
        if other.account_type != "EXPENSE":
            raise HTTPException(422, "Use Payments for invoice settlement; direct cashier payments require an expense account")
    elif other.account_type not in ("REVENUE", "INCOME") or other.account_number != "400":
        raise HTTPException(422, "Direct receipts use revenue account 400; settle customer invoices through customer payments")
    return cash, other


@router.get("")
def listing(date_from: date, date_to: date, location_id: int | None = None,
            petty_cash: bool = False, page: int = Query(1, ge=1),
            page_size: int = Query(100, ge=1, le=100), db: Session = Depends(get_db), user=Depends(view)):
    location_id = resolve_location_id(user, location_id)
    q = db.query(JournalEntry).filter(JournalEntry.reference_type == SOURCE,
        JournalEntry.posting_date.between(date_from, date_to))
    if location_id is not None:
        q = q.filter(JournalEntry.location_id == location_id)
    if petty_cash:
        q = q.filter(JournalEntry.lines.any(JournalLine.account.has(ChartOfAccount.account_subtype == "PETTY_CASH")))
    count = q.count()
    return dict(items=[serialize(j, user) for j in q.order_by(JournalEntry.posting_date.desc(), JournalEntry.id.desc()).offset((page - 1) * page_size).limit(page_size)],
        total_items=count, total_pages=max(1, ceil(count / page_size)), page=page, page_size=page_size)


@router.post("", status_code=201)
def create(data: CashEntry, db: Session = Depends(get_db), user=Depends(manage)):
    from app.services.fiscal_period_service import FiscalPeriodService
    FiscalPeriodService.validate_posting_date(db, data.posting_date)
    cash, other = validate_accounts(db, data)
    location_id = resolve_location_id(user, data.location_id)
    validate_dimensions(db, data.business_unit_id, location_id, data.department_id)
    number = next_document_number(db, "GC", digits=6)
    journal = JournalEntry(journal_number=number, posting_date=data.posting_date, status="DRAFT",
        reference_type=SOURCE, reference_id=0, document_type=f"CASHIER_{data.operation}", document_number=number,
        description=f"{data.reference_number}: {data.description}", created_by_id=user.id,
        business_unit_id=data.business_unit_id, location_id=location_id, department_id=data.department_id)
    debit_account, credit_account = (cash, other) if data.operation == "RECEIPT" else (other, cash)
    for index, (account, debit, credit) in enumerate(((debit_account, data.amount, 0), (credit_account, 0, data.amount)), 1):
        journal.lines.append(JournalLine(line_number=index, account_id=account.id, debit=debit, credit=credit,
            description=data.description, business_unit_id=data.business_unit_id, location_id=location_id,
            department_id=data.department_id, cash_flow_category="OPERATING" if data.operation != "TRANSFER" else None,
            cash_flow_direction=("INFLOW" if data.operation == "RECEIPT" else "OUTFLOW") if data.operation != "TRANSFER" else None))
    db.add(journal)
    db.flush()
    journal.reference_id = journal.id
    record_audit(db, user, "CASHIER_DRAFT_CREATED", "JOURNAL_ENTRY", f"Created {number}", entity_id=journal.id,
        after_data=data.model_dump(mode="json"))
    db.commit()
    return serialize(journal, user)


@router.post("/{entry_id}/post")
def post(entry_id: int, db: Session = Depends(get_db), user=Depends(manage)):
    journal = db.query(JournalEntry).filter(JournalEntry.id == entry_id, JournalEntry.reference_type == SOURCE).with_for_update().first()
    if not journal:
        raise HTTPException(404, "Cashier entry not found")
    enforce_location_access(user, journal.location_id)
    if journal.status != "POSTED":
        post_locked_journal(db, journal=journal, user=user)
        db.commit()
    return serialize(journal, user)


@router.post("/{entry_id}/void")
def void(entry_id: int, db: Session = Depends(get_db), user=Depends(manage)):
    journal = db.query(JournalEntry).filter(JournalEntry.id == entry_id, JournalEntry.reference_type == SOURCE).with_for_update().first()
    if not journal:
        raise HTTPException(404, "Cashier entry not found")
    enforce_location_access(user, journal.location_id)
    if journal.status != "DRAFT":
        raise HTTPException(409, "Only a draft cashier entry can be voided")
    journal.status = "VOID"
    record_audit(db, user, "CASHIER_DRAFT_VOIDED", "JOURNAL_ENTRY", f"Voided {journal.journal_number}", entity_id=journal.id)
    db.commit()
    return serialize(journal, user)
