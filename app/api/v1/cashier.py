"""Cashier draft and posting flows backed by the existing journal ledger."""
from datetime import date, datetime, timezone
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
from app.services.organization_access import resolve_organization_access, effective_business_unit
from app.models.general_ledger import GeneralLedger
from app.services.organization_dimensions import validate_dimensions
from app.api.v1.journals import post_locked_journal, serialize

router = APIRouter(prefix="/cashier", tags=["General Cashier"])
view = require_permission("finance.view")
manage = require_permission("finance.manage")
CASH = {"BANK", "CASH", "PETTY_CASH"}
SOURCE = "GENERAL_CASHIER"


class CashEntry(BaseModel):
    posting_date: date
    operation: Literal["RECEIPT", "PAYMENT", "TRANSFER", "REPLENISHMENT"]
    cash_account_id: int
    counterpart_account_id: int
    amount: Decimal = Field(gt=0, decimal_places=2, max_digits=18)
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
    if cash.account_type != "ASSET" or cash.account_subtype not in CASH or cash.normal_balance != "DEBIT":
        raise HTTPException(422, "Select a cash, bank or petty-cash account")
    if data.operation in ("TRANSFER", "REPLENISHMENT"):
        if other.account_type != "ASSET" or other.account_subtype not in CASH or other.normal_balance != "DEBIT":
            raise HTTPException(422, "Transfers require two cash/bank accounts")
    elif data.operation == "PAYMENT":
        if other.account_type != "EXPENSE" or other.normal_balance != "DEBIT":
            raise HTTPException(422, "Use Payments for invoice settlement; direct cashier payments require an expense account")
    elif other.account_type not in ("REVENUE", "INCOME") or other.normal_balance != "CREDIT":
        raise HTTPException(422, "Direct receipts require a revenue account; settle customer invoices through customer payments")
    return cash, other


def scoped_query(db, user, location_id=None):
    scope = resolve_organization_access(db, user, location_id=location_id)
    query = db.query(JournalEntry).filter(JournalEntry.reference_type == SOURCE)
    for key, value in scope.items():
        if value is not None:
            column = effective_business_unit(JournalEntry.business_unit_id, JournalEntry.location_id) if key == 'business_unit_id' else getattr(JournalEntry, key)
            query = query.filter(column == value)
    return query


def entry_data(journal):
    if len(journal.lines) != 2: raise HTTPException(409, 'Cashier entry must contain exactly two source lines')
    operation = (journal.document_type or '').removeprefix('CASHIER_')
    if operation not in ('PAYMENT', 'RECEIPT', 'TRANSFER', 'REPLENISHMENT'): raise HTTPException(409, 'Unknown cashier operation')
    debits = [line for line in journal.lines if line.debit > 0 and line.credit == 0]
    credits = [line for line in journal.lines if line.credit > 0 and line.debit == 0]
    if len(debits) != 1 or len(credits) != 1 or debits[0].debit != credits[0].credit:
        raise HTTPException(409, 'Cashier source lines are not balanced')
    incoming = operation in ('RECEIPT', 'REPLENISHMENT')
    cash, other = (debits[0], credits[0]) if incoming else (credits[0], debits[0])
    description = cash.description or other.description or ''
    suffix = ': ' + description
    reference = journal.external_reference or (journal.description[:-len(suffix)] if description and (journal.description or '').endswith(suffix) else journal.document_number)
    return CashEntry(posting_date=journal.posting_date, operation=operation, cash_account_id=cash.account_id,
        counterpart_account_id=other.account_id, amount=debits[0].debit, location_id=journal.location_id,
        business_unit_id=journal.business_unit_id, department_id=journal.department_id,
        reference_number=reference, description=description)


def payload(journal, user):
    # Keep malformed legacy rows visible for finance inspection; posting/editing
    # still requires a valid, balanced source structure.
    result = serialize(journal, user)
    try: result['entry'] = entry_data(journal).model_dump(mode='json')
    except HTTPException as exc: result.update(entry=None, source_integrity_error=exc.detail)
    return result


def get_entry(db, user, entry_id, lock=False):
    query = scoped_query(db, user).filter(JournalEntry.id == entry_id)
    journal = (query.with_for_update() if lock else query).first()
    if not journal: raise HTTPException(404, 'Cashier entry not found')
    return journal


def set_draft(db, journal, data, user):
    from app.services.fiscal_period_service import FiscalPeriodService
    from app.models.location import Location
    FiscalPeriodService.validate_posting_date(db, data.posting_date)
    scope = resolve_organization_access(db, user, location_id=data.location_id,
        business_unit_id=data.business_unit_id, department_id=data.department_id)
    if scope['business_unit_id'] is None:
        location = db.get(Location, scope['location_id'])
        scope['business_unit_id'] = location.business_unit_id if location else None
    data = data.model_copy(update=scope)
    validate_dimensions(db, data.business_unit_id, data.location_id, data.department_id)
    cash, other = validate_accounts(db, data)
    journal.posting_date = data.posting_date
    journal.document_type = f'CASHIER_{data.operation}'
    journal.description = f'{data.reference_number}: {data.description}'
    journal.external_reference = data.reference_number
    journal.business_unit_id = data.business_unit_id
    journal.location_id = data.location_id
    journal.department_id = data.department_id
    incoming = data.operation in ('RECEIPT', 'REPLENISHMENT')
    transfer = data.operation in ('TRANSFER', 'REPLENISHMENT')
    debit, credit = (cash, other) if incoming else (other, cash)
    journal.lines.clear()
    for index, (account, dr, cr) in enumerate(((debit, data.amount, 0), (credit, 0, data.amount)), 1):
        journal.lines.append(JournalLine(line_number=index, account_id=account.id, debit=dr, credit=cr,
            description=data.description, business_unit_id=data.business_unit_id, location_id=data.location_id,
            department_id=data.department_id, cash_flow_category=None if transfer else 'OPERATING',
            cash_flow_direction=None if transfer else 'INFLOW' if incoming else 'OUTFLOW'))
    return data


@router.get('')
def listing(date_from: date, date_to: date, location_id: int | None = None,
            petty_cash: bool = False, page: int = Query(1, ge=1),
            page_size: int = Query(100, ge=1, le=100), db: Session = Depends(get_db), user=Depends(view)):
    if date_from > date_to: raise HTTPException(422, 'From date must be before To date')
    q = scoped_query(db, user, location_id).filter(JournalEntry.posting_date.between(date_from, date_to))
    if petty_cash: q = q.filter(JournalEntry.lines.any(JournalLine.account.has(ChartOfAccount.account_subtype == 'PETTY_CASH')))
    count = q.count()
    return dict(items=[payload(j, user) for j in q.order_by(JournalEntry.posting_date.desc(), JournalEntry.id.desc()).offset((page - 1) * page_size).limit(page_size)],
        total_items=count, total_pages=max(1, ceil(count / page_size)), page=page, page_size=page_size)


@router.get('/{entry_id}')
def detail(entry_id: int, db: Session = Depends(get_db), user=Depends(view)):
    return payload(get_entry(db, user, entry_id), user)


@router.post('', status_code=201)
def create(data: CashEntry, db: Session = Depends(get_db), user=Depends(manage)):
    number = next_document_number(db, 'GC', digits=6)
    journal = JournalEntry(journal_number=number, posting_date=data.posting_date, status='DRAFT',
        reference_type=SOURCE, reference_id=0, document_number=number, created_by_id=user.id)
    data = set_draft(db, journal, data, user)
    db.add(journal); db.flush()
    journal.reference_id = journal.id
    record_audit(db, user, 'CASHIER_DRAFT_CREATED', 'JOURNAL_ENTRY', f'Created {number}', entity_id=journal.id, after_data=data.model_dump(mode='json'))
    db.commit()
    return payload(journal, user)


@router.patch('/{entry_id}')
def update(entry_id: int, data: CashEntry, db: Session = Depends(get_db), user=Depends(manage)):
    journal = get_entry(db, user, entry_id, lock=True)
    if journal.status != 'DRAFT': raise HTTPException(409, 'Only draft cashier entries can be edited')
    if db.query(GeneralLedger.id).filter(GeneralLedger.reference_type == SOURCE, GeneralLedger.reference_id == journal.id).first():
        raise HTTPException(409, 'Cashier entry still has posted accounting; inspect before editing')
    before = entry_data(journal).model_dump(mode='json')
    data = set_draft(db, journal, data, user)
    record_audit(db, user, 'CASHIER_DRAFT_UPDATED', 'JOURNAL_ENTRY', f'Updated {journal.journal_number}', entity_id=journal.id,
        before_data=before, after_data=data.model_dump(mode='json'))
    db.commit()
    return payload(journal, user)


def validate_cashier_journal(db, journal, user):
    data = entry_data(journal)
    validate_accounts(db, data)
    scope = resolve_organization_access(db, user, location_id=data.location_id, business_unit_id=data.business_unit_id, department_id=data.department_id)
    if scope['department_id'] is not None and data.department_id != scope['department_id']:
        raise HTTPException(404, 'Cashier entry not found')
    if any(any(getattr(line,k) != getattr(journal,k) for k in ('location_id','business_unit_id','department_id')) for line in journal.lines):
        raise HTTPException(409, 'Cashier line organization differs from its source')
    if db.query(GeneralLedger.id).filter(GeneralLedger.reference_type == SOURCE, GeneralLedger.reference_id == journal.id).first():
        raise HTTPException(409, 'Cashier entry already has ledger rows')


@router.post('/{entry_id}/post')
def post(entry_id: int, db: Session = Depends(get_db), user=Depends(manage)):
    journal = get_entry(db, user, entry_id, lock=True)
    if journal.status != 'POSTED':
        post_locked_journal(db, journal=journal, user=user)
        db.commit()
    return payload(journal, user)


@router.post('/{entry_id}/void')
def void(entry_id: int, db: Session = Depends(get_db), user=Depends(manage)):
    journal = get_entry(db, user, entry_id, lock=True)
    if journal.status != 'DRAFT': raise HTTPException(409, 'Only a draft cashier entry can be voided')
    if db.query(GeneralLedger.id).filter(GeneralLedger.reference_type == SOURCE, GeneralLedger.reference_id == journal.id).first():
        raise HTTPException(409, 'Cashier entry still has ledger rows')
    journal.status = 'VOID'; journal.voided_at = datetime.now(timezone.utc)
    record_audit(db, user, 'CASHIER_DRAFT_VOIDED', 'JOURNAL_ENTRY', f'Voided {journal.journal_number}', entity_id=journal.id)
    db.commit()
    return payload(journal, user)
