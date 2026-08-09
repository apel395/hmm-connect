from datetime import date, datetime, timezone
from decimal import Decimal
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_any_role
from app.models.chart_of_account import ChartOfAccount
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.supplier_invoice import SupplierInvoice
from app.schemas.journal import JournalCreate, JournalUpdate
from app.services.audit import record_audit
from app.services.document_context import print_metadata
from app.services.document_number import next_document_number
from app.services.general_ledger import GeneralLedgerService
from app.services.organization_dimensions import validate_dimensions

router = APIRouter(prefix="/journal-entries", tags=["Journal Entries"])
ZERO = Decimal("0")


def access(user):
    if not has_any_role(user, "FINANCE"):
        raise HTTPException(403, "Finance access required")


def get(db, id):
    value = db.get(JournalEntry, id)
    if not value:
        raise HTTPException(404, "Journal entry not found")
    return value


def validate_lines(db, lines):
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


def normalize_line(line, business_unit_id, location_id, department_id):
    values = line.model_dump()
    values["business_unit_id"] = business_unit_id
    values["location_id"] = location_id
    values["department_id"] = department_id
    return values


def serialize(value):
    debit = sum((Decimal(line.debit) for line in value.lines), ZERO)
    credit = sum((Decimal(line.credit) for line in value.lines), ZERO)
    return {
        "id": value.id,
        "journal_number": value.journal_number,
        "journal_date": value.posting_date,
        "posting_date": value.posting_date,
        "description": value.description,
        "reference_type": value.reference_type,
        "reference_id": value.reference_id,
        "reference_number": value.document_number,
        "status": value.status,
        "business_unit_id": value.business_unit_id,
        "business_unit_name": value.business_unit.name if getattr(value, "business_unit", None) else None,
        "department_id": value.department_id,
        "department_name": value.department.name if getattr(value, "department", None) else None,
        "location_id": value.location_id,
        "location_name": value.location.name if getattr(value, "location", None) else None,
        "created_by_name": value.created_by.full_name if value.created_by else None,
        "posted_by_name": value.posted_by.full_name if value.posted_by else None,
        "created_at": value.created_at,
        "posted_at": value.posted_at,
        "voided_at": value.voided_at,
        "total_debit": debit,
        "total_credit": credit,
        "difference": debit - credit,
        "allowed_actions": {
            "can_edit": value.status == "DRAFT",
            "can_post": value.status == "DRAFT" and bool(value.lines) and debit == credit,
            "can_void": value.status == "DRAFT",
            "can_print": True,
        },
        "lines": [
            {
                "id": line.id,
                "line_number": line.line_number,
                "account_id": line.account_id,
                "account_code": line.account.account_number,
                "account_name": line.account.account_name,
                "description": line.description,
                "debit": line.debit,
                "credit": line.credit,
                "business_unit_id": line.business_unit_id,
                "department_id": line.department_id,
                "department_name": line.department.name if line.department else None,
                "location_id": line.location_id,
                "location_name": line.location.name if line.location else None,
                "supplier_id": line.supplier_id,
            }
            for line in value.lines
        ],
    }


@router.get("")
def listing(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), search: str | None = None,
    status: str | None = None, date_from: date | None = None, date_to: date | None = None,
    reference_type: str | None = None, account_id: int | None = None,
    db: Session = Depends(get_db), _=Depends(get_current_user),
):
    query = db.query(JournalEntry)
    if search:
        query = query.filter(or_(JournalEntry.journal_number.ilike(f"%{search}%"), JournalEntry.document_number.ilike(f"%{search}%"), JournalEntry.description.ilike(f"%{search}%")))
    if status:
        query = query.filter(JournalEntry.status == status)
    if date_from:
        query = query.filter(JournalEntry.posting_date >= date_from)
    if date_to:
        query = query.filter(JournalEntry.posting_date <= date_to)
    if reference_type:
        query = query.filter(JournalEntry.reference_type == reference_type)
    if account_id:
        query = query.join(JournalEntry.lines).filter(JournalLine.account_id == account_id)
    total = query.count()
    rows = query.order_by(JournalEntry.posting_date.desc(), JournalEntry.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [serialize(row) for row in rows], "page": page, "page_size": page_size, "total_items": total, "total_pages": ceil(total / page_size) if total else 0, "has_next": page * page_size < total, "has_previous": page > 1}


@router.post("", status_code=201)
def create(data: JournalCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    validate_dimensions(db, data.business_unit_id, data.location_id, data.department_id, required=True)
    debit, credit = validate_lines(db, data.lines)
    if debit != credit:
        raise HTTPException(422, "Journal debit and credit must be balanced")
    value = JournalEntry(
        journal_number=next_document_number(db, "JV"), posting_date=data.posting_date,
        document_type=data.document_type, document_number=data.document_number,
        reference_type=data.reference_type, reference_id=data.reference_id, description=data.description,
        status="DRAFT", created_by_id=user.id, business_unit_id=data.business_unit_id,
        location_id=data.location_id, department_id=data.department_id,
    )
    for index, line in enumerate(data.lines, 1):
        value.lines.append(JournalLine(line_number=index, **normalize_line(line, data.business_unit_id, data.location_id, data.department_id)))
    db.add(value)
    db.flush()
    record_audit(db, user, "JOURNAL_CREATED", "JOURNAL_ENTRY", f"Created {value.journal_number}", entity_id=value.id, reference_document=value.document_number)
    db.commit()
    db.refresh(value)
    return serialize(value)


@router.get("/{journal_id}")
def detail(journal_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    return serialize(get(db, journal_id))


@router.patch("/{journal_id}")
def update(journal_id: int, data: JournalUpdate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    value = get(db, journal_id)
    if value.status != "DRAFT":
        raise HTTPException(409, "Only draft journals can be edited")
    business_unit_id = data.business_unit_id if data.business_unit_id is not None else value.business_unit_id
    location_id = data.location_id if data.location_id is not None else value.location_id
    department_id = data.department_id if data.department_id is not None else value.department_id
    validate_dimensions(db, business_unit_id, location_id, department_id, required=True)
    if data.posting_date:
        value.posting_date = data.posting_date
    if data.description is not None:
        value.description = data.description
    value.business_unit_id = business_unit_id
    value.location_id = location_id
    value.department_id = department_id
    if data.lines is not None:
        validate_lines(db, data.lines)
        value.lines.clear()
        for index, line in enumerate(data.lines, 1):
            value.lines.append(JournalLine(line_number=index, **normalize_line(line, business_unit_id, location_id, department_id)))
    else:
        for line in value.lines:
            line.business_unit_id = business_unit_id
            line.location_id = location_id
            line.department_id = department_id
    record_audit(db, user, "JOURNAL_UPDATED", "JOURNAL_ENTRY", f"Updated {value.journal_number}", entity_id=value.id)
    db.commit()
    db.refresh(value)
    return serialize(value)


@router.post("/{journal_id}/post")
def post(journal_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    value = db.query(JournalEntry).filter(JournalEntry.id == journal_id).with_for_update().first()
    if not value:
        raise HTTPException(404, "Journal entry not found")
    if value.status != "DRAFT":
        raise HTTPException(409, "Only draft journals can be posted")
    validate_dimensions(db, value.business_unit_id, value.location_id, value.department_id, required=True)
    debit, credit = validate_lines(db, value.lines)
    if debit != credit:
        raise HTTPException(409, "Journal is not balanced")
    for line in value.lines:
        GeneralLedgerService.post(
            db=db, account_id=line.account_id, debit=line.debit, credit=line.credit,
            posting_date=value.posting_date, journal_source=value.reference_type,
            document_type=value.document_type, document_number=value.document_number,
            reference_type=value.reference_type, reference_id=value.reference_id,
            reference_number=value.journal_number, description=line.description, user_id=user.id,
        )
    value.status = "POSTED"
    value.posted_by_id = user.id
    value.posted_at = datetime.now(timezone.utc)
    if value.reference_type == "SUPPLIER_INVOICE":
        invoice = db.get(SupplierInvoice, value.reference_id)
        if invoice:
            invoice.status = "POSTED"
            invoice.posted_at = value.posted_at
    record_audit(db, user, "JOURNAL_POSTED", "JOURNAL_ENTRY", f"Posted {value.journal_number}", entity_id=value.id, reference_document=value.document_number)
    db.commit()
    db.refresh(value)
    return serialize(value)


@router.post("/{journal_id}/void")
def void(journal_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    value = get(db, journal_id)
    if value.status != "DRAFT":
        raise HTTPException(409, "Only draft journals can be voided without reversal")
    value.status = "VOID"
    value.voided_at = datetime.now(timezone.utc)
    record_audit(db, user, "JOURNAL_VOIDED", "JOURNAL_ENTRY", f"Voided {value.journal_number}", entity_id=value.id)
    db.commit()
    db.refresh(value)
    return serialize(value)


@router.get("/{journal_id}/print")
def printable(journal_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return {**serialize(get(db, journal_id)), "document_type": "Journal Entry", **print_metadata(user)}
