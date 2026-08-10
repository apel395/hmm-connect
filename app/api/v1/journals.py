from datetime import date, datetime, timezone
from decimal import Decimal
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_any_role, is_superuser
from app.models.chart_of_account import ChartOfAccount
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.schemas.journal import JournalCreate, JournalUpdate
from app.services.accounting_unpost import (
    SUPPORTED_SOURCE_TYPES,
    apply_source_post_state,
    unpost_journal,
)
from app.services.audit import record_audit
from app.services.document_context import print_metadata
from app.services.document_number import next_document_number
from app.services.general_ledger import GeneralLedgerService

router = APIRouter(prefix="/journal-entries", tags=["Journal Entries"])
ZERO = Decimal("0")
STANDARD_UNPOSTABLE_SOURCES = {"MANUAL", "SUPPLIER_INVOICE"}


def access(user):
    if not has_any_role(user, "FINANCE"):
        raise HTTPException(403, "Finance access required")


def get(db, id):
    x = db.get(JournalEntry, id)
    if not x:
        raise HTTPException(404, "Journal entry not found")
    return x


def validate(db, lines):
    if not lines:
        raise HTTPException(400, "Journal must contain at least one line")
    debit = credit = ZERO
    for line in lines:
        d = Decimal(line.debit)
        c = Decimal(line.credit)
        if d < 0 or c < 0:
            raise HTTPException(400, "Debit and credit cannot be negative")
        if (d > 0) == (c > 0):
            raise HTTPException(400, "Each line must contain either debit or credit")
        account = db.get(ChartOfAccount, line.account_id)
        if not account or not account.is_active or not account.is_posting:
            raise HTTPException(400, "Journal lines require active posting accounts")
        debit += d
        credit += c
    return debit, credit


def serialize(x, user=None):
    debit = sum((Decimal(l.debit) for l in x.lines), ZERO)
    credit = sum((Decimal(l.credit) for l in x.lines), ZERO)
    source = (x.reference_type or "MANUAL").upper()
    admin_unpost = bool(user and is_superuser(user) and source in SUPPORTED_SOURCE_TYPES)
    return {
        "id": x.id,
        "journal_number": x.journal_number,
        "journal_date": x.posting_date,
        "posting_date": x.posting_date,
        "description": x.description,
        "reference_type": x.reference_type,
        "reference_id": x.reference_id,
        "reference_number": x.document_number,
        "status": x.status,
        "created_by_name": x.created_by.full_name if x.created_by else None,
        "posted_by_name": x.posted_by.full_name if x.posted_by else None,
        "created_at": x.created_at,
        "posted_at": x.posted_at,
        "voided_at": x.voided_at,
        "total_debit": debit,
        "total_credit": credit,
        "difference": debit - credit,
        "allowed_actions": {
            "can_edit": x.status == "DRAFT",
            "can_post": x.status == "DRAFT" and bool(x.lines) and debit == credit,
            "can_unpost": x.status == "POSTED" and (
                source in STANDARD_UNPOSTABLE_SOURCES or admin_unpost
            ),
            "can_void": x.status == "DRAFT",
            "can_print": True,
        },
        "lines": [
            {
                "id": l.id,
                "line_number": l.line_number,
                "account_id": l.account_id,
                "account_code": l.account.account_number,
                "account_name": l.account.account_name,
                "description": l.description,
                "debit": l.debit,
                "credit": l.credit,
                "department_id": l.department_id,
                "department_name": l.department.name if l.department else None,
                "location_id": l.location_id,
                "location_name": l.location.name if l.location else None,
                "supplier_id": l.supplier_id,
            }
            for l in x.lines
        ],
    }


@router.get("")
def listing(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    reference_type: str | None = None,
    account_id: int | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    q = db.query(JournalEntry)
    if search:
        q = q.filter(or_(
            JournalEntry.journal_number.ilike(f"%{search}%"),
            JournalEntry.document_number.ilike(f"%{search}%"),
            JournalEntry.description.ilike(f"%{search}%"),
        ))
    if status:
        q = q.filter(JournalEntry.status == status)
    if date_from:
        q = q.filter(JournalEntry.posting_date >= date_from)
    if date_to:
        q = q.filter(JournalEntry.posting_date <= date_to)
    if reference_type:
        q = q.filter(JournalEntry.reference_type == reference_type)
    if account_id:
        q = q.join(JournalEntry.lines).filter(JournalLine.account_id == account_id)
    total = q.count()
    rows = q.order_by(JournalEntry.posting_date.desc(), JournalEntry.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [serialize(x, user) for x in rows],
        "page": page,
        "page_size": page_size,
        "total_items": total,
        "total_pages": ceil(total / page_size) if total else 0,
        "has_next": page * page_size < total,
        "has_previous": page > 1,
    }


@router.post("", status_code=201)
def create(data: JournalCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    debit, credit = validate(db, data.lines)
    if debit != credit:
        raise HTTPException(422, "Journal debit and credit must be balanced")
    x = JournalEntry(
        journal_number=next_document_number(db, "MAN", digits=6),
        posting_date=data.posting_date,
        document_type=data.document_type,
        document_number=data.document_number,
        reference_type=data.reference_type,
        reference_id=data.reference_id,
        description=data.description,
        status="DRAFT",
        created_by_id=user.id,
        business_unit_id=data.business_unit_id,
        location_id=data.location_id,
        department_id=data.department_id,
    )
    for i, line in enumerate(data.lines, 1):
        x.lines.append(JournalLine(line_number=i, **line.model_dump()))
    db.add(x)
    db.flush()
    record_audit(db, user, "JOURNAL_CREATED", "JOURNAL_ENTRY", f"Created {x.journal_number}", entity_id=x.id, reference_document=x.document_number)
    db.commit()
    db.refresh(x)
    return serialize(x, user)


@router.get("/{journal_id}")
def detail(journal_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return serialize(get(db, journal_id), user)


@router.patch("/{journal_id}")
def update(journal_id: int, data: JournalUpdate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    x = get(db, journal_id)
    if x.status != "DRAFT":
        raise HTTPException(409, "Unpost the journal before editing it")
    if data.posting_date:
        x.posting_date = data.posting_date
    if data.description is not None:
        x.description = data.description
    if data.lines is not None:
        validate(db, data.lines)
        x.lines.clear()
        for i, l in enumerate(data.lines, 1):
            x.lines.append(JournalLine(line_number=i, **l.model_dump()))
    record_audit(db, user, "JOURNAL_UPDATED", "JOURNAL_ENTRY", f"Updated {x.journal_number}", entity_id=x.id)
    db.commit()
    db.refresh(x)
    return serialize(x, user)


@router.post("/{journal_id}/post")
def post(journal_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    x = db.query(JournalEntry).filter(JournalEntry.id == journal_id).with_for_update().first()
    if not x:
        raise HTTPException(404, "Journal entry not found")
    if x.status != "DRAFT":
        raise HTTPException(409, "Only draft journals can be posted")
    debit, credit = validate(db, x.lines)
    if debit != credit:
        raise HTTPException(409, "Journal is not balanced")

    # If this journal was generated by an operational document and previously
    # unposted, revalidate and restore that source state in the same transaction.
    apply_source_post_state(db, journal=x, user=user)

    for l in x.lines:
        GeneralLedgerService.post(
            db=db,
            account_id=l.account_id,
            debit=l.debit,
            credit=l.credit,
            posting_date=x.posting_date,
            journal_source=x.reference_type,
            document_type=x.document_type,
            document_number=x.document_number,
            reference_type=x.reference_type,
            reference_id=x.reference_id,
            reference_number=x.journal_number,
            description=l.description,
            user_id=user.id,
        )
    x.status = "POSTED"
    x.posted_by_id = user.id
    x.posted_at = datetime.now(timezone.utc)
    record_audit(db, user, "JOURNAL_POSTED", "JOURNAL_ENTRY", f"Posted {x.journal_number}", entity_id=x.id, reference_document=x.document_number)
    db.commit()
    db.refresh(x)
    return serialize(x, user)


@router.post("/{journal_id}/unpost")
def unpost(journal_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    x = db.query(JournalEntry).filter(JournalEntry.id == journal_id).with_for_update().first()
    if not x:
        raise HTTPException(404, "Journal entry not found")
    source = (x.reference_type or "MANUAL").upper()
    if source not in STANDARD_UNPOSTABLE_SOURCES and not is_superuser(user):
        raise HTTPException(403, "Only an administrator can unpost a source-controlled journal")
    return serialize(unpost_journal(db, journal=x, user=user), user)


@router.post("/{journal_id}/void")
def void(journal_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    x = get(db, journal_id)
    if x.status != "DRAFT":
        raise HTTPException(409, "Only draft journals can be voided without reversal")
    x.status = "VOID"
    x.voided_at = datetime.now(timezone.utc)
    record_audit(db, user, "JOURNAL_VOIDED", "JOURNAL_ENTRY", f"Voided {x.journal_number}", entity_id=x.id)
    db.commit()
    db.refresh(x)
    return serialize(x, user)


@router.get("/{journal_id}/print")
def printable(journal_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return {**serialize(get(db, journal_id), user), "document_type": "Journal Entry", **print_metadata(user)}
