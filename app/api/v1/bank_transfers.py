from math import ceil
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_permission
from app.models.bank_transfer import BankTransfer
from app.models.chart_of_account import ChartOfAccount
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.schemas.bank_transfer import BankTransferInput
from app.services.audit import record_audit
from app.services.document_context import print_metadata
from app.services.document_number import next_document_number

router = APIRouter(prefix="/bank-transfers", tags=["Bank Transfers"])
CASH_TYPES = {"CASH", "BANK", "PETTY_CASH"}


def access(user):
    if not has_permission(user, "finance.manage"):
        raise HTTPException(403, "Finance access required")


def get(db, id):
    item = db.get(BankTransfer, id)
    if not item:
        raise HTTPException(404, "Bank transfer not found")
    return item


def account(db, id):
    item = db.get(ChartOfAccount, id)
    if not item or item.account_type != "ASSET" or item.account_subtype not in CASH_TYPES or not item.is_active or not item.is_posting:
        raise HTTPException(400, "Transfer accounts must be active cash/bank posting accounts")
    return item


def validate(db, data):
    source = account(db, data.source_account_id)
    destination = account(db, data.destination_account_id)
    if source.id == destination.id:
        raise HTTPException(400, "Source and destination accounts must differ")
    return source, destination


def serialize(item):
    return {
        "id": item.id,
        "transfer_number": item.transfer_number,
        "transfer_date": item.transfer_date,
        "source_account_id": item.source_account_id,
        "source_account_code": item.source_account.account_number,
        "source_account_name": item.source_account.account_name,
        "destination_account_id": item.destination_account_id,
        "destination_account_code": item.destination_account.account_number,
        "destination_account_name": item.destination_account.account_name,
        "amount": item.amount,
        "currency": item.currency,
        "reference_number": item.reference_number,
        "notes": item.notes,
        "status": item.status,
        "journal_entry_id": item.journal_entry_id,
        "journal_number": item.journal_entry.journal_number if item.journal_entry else None,
        "created_by_name": item.created_by.full_name if item.created_by else None,
        "posted_by_name": item.posted_by.full_name if item.posted_by else None,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "posted_at": item.posted_at,
        "allowed_actions": {
            "can_edit": item.status == "DRAFT" and not item.journal_entry_id,
            "can_generate_journal": item.status == "DRAFT" and not item.journal_entry_id,
            "can_post": False,
            "can_print": True,
        },
    }


@router.get("")
def listing(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), status: str | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    query = db.query(BankTransfer)
    if status:
        query = query.filter(BankTransfer.status == status)
    total = query.count()
    items = query.order_by(BankTransfer.transfer_date.desc(), BankTransfer.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [serialize(x) for x in items], "page": page, "page_size": page_size, "total_items": total, "total_pages": ceil(total / page_size) if total else 0, "has_next": page * page_size < total, "has_previous": page > 1}


@router.get("/{transfer_id}")
def detail(transfer_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    return serialize(get(db, transfer_id))


@router.post("", status_code=201)
def create(data: BankTransferInput, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    validate(db, data)
    item = BankTransfer(transfer_number=next_document_number(db, "BT"), status="DRAFT", created_by_id=user.id, **data.model_dump())
    db.add(item)
    db.flush()
    record_audit(db, user, "BANK_TRANSFER_CREATED", "BANK_TRANSFER", f"Created {item.transfer_number}", entity_id=item.id)
    db.commit()
    db.refresh(item)
    return serialize(item)


@router.patch("/{transfer_id}")
def update(transfer_id: int, data: BankTransferInput, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    item = get(db, transfer_id)
    if item.status != "DRAFT" or item.journal_entry_id:
        raise HTTPException(409, "Only draft transfers without a journal can be edited")
    validate(db, data)
    for key, value in data.model_dump().items():
        setattr(item, key, value)
    record_audit(db, user, "BANK_TRANSFER_UPDATED", "BANK_TRANSFER", f"Updated {item.transfer_number}", entity_id=item.id)
    db.commit()
    db.refresh(item)
    return serialize(item)


@router.post("/{transfer_id}/generate-journal")
def generate_journal(transfer_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    item = db.query(BankTransfer).filter(BankTransfer.id == transfer_id).with_for_update().first()
    if not item or item.status != "DRAFT":
        raise HTTPException(409, "Only draft transfers can generate a journal")
    if item.journal_entry_id:
        raise HTTPException(409, "Bank transfer already has a journal")
    source, destination = validate(db, BankTransferInput(
        transfer_date=item.transfer_date,
        source_account_id=item.source_account_id,
        destination_account_id=item.destination_account_id,
        amount=item.amount,
        currency=item.currency,
        reference_number=item.reference_number,
        notes=item.notes,
    ))
    journal = JournalEntry(
        journal_number=next_document_number(db, "BTR", digits=6),
        posting_date=item.transfer_date,
        status="DRAFT",
        document_type="BANK_TRANSFER",
        document_number=item.transfer_number,
        reference_type="BANK_TRANSFER",
        reference_id=item.id,
        description=f"Internal transfer {item.transfer_number}",
        created_by_id=user.id,
    )
    journal.lines = [
        JournalLine(line_number=1, account_id=destination.id, debit=item.amount, credit=0, description=f"Transfer from {source.account_number}", cash_flow_category="NON_CASH", cash_flow_direction="TRANSFER"),
        JournalLine(line_number=2, account_id=source.id, debit=0, credit=item.amount, description=f"Transfer to {destination.account_number}", cash_flow_category="NON_CASH", cash_flow_direction="TRANSFER"),
    ]
    db.add(journal)
    db.flush()
    item.journal_entry_id = journal.id
    record_audit(db, user, "BANK_TRANSFER_JOURNAL_GENERATED", "BANK_TRANSFER", f"Generated {journal.journal_number} for {item.transfer_number}", entity_id=item.id, reference_document=journal.journal_number)
    db.commit()
    db.refresh(item)
    return serialize(item)


@router.post("/{transfer_id}/post")
def post_disabled(transfer_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    get(db, transfer_id)
    raise HTTPException(409, "Post the related journal from the Journal page")


@router.get("/{transfer_id}/allowed-actions")
def actions(transfer_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    return serialize(get(db, transfer_id))["allowed_actions"]


@router.get("/{transfer_id}/print")
def printable(transfer_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    return {**serialize(get(db, transfer_id)), "document_type": "Bank Transfer", **print_metadata(user)}
