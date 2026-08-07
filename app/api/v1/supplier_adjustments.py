from datetime import date, datetime, timezone
from decimal import Decimal
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_any_role
from app.models.account_payable import AccountPayable
from app.models.accounting_posting_rule import AccountingPostingRule
from app.models.chart_of_account import ChartOfAccount
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.supplier_adjustment import SupplierAdjustment
from app.models.supplier_invoice import SupplierInvoice
from app.schemas.supplier_adjustment import SupplierAdjustmentCreate, SupplierAdjustmentUpdate
from app.services.audit import record_audit
from app.services.document_number import next_document_number
from app.services.general_ledger import GeneralLedgerService

router = APIRouter(prefix="/supplier-adjustments", tags=["Supplier Adjustments"])
ZERO = Decimal("0")


def access(user):
    if not has_any_role(user, "FINANCE"):
        raise HTTPException(403, "Finance access required")


def get_adjustment(db: Session, adjustment_id: int) -> SupplierAdjustment:
    adjustment = db.get(SupplierAdjustment, adjustment_id)
    if not adjustment:
        raise HTTPException(404, "Supplier adjustment not found")
    return adjustment


def validate_account(db: Session, account_id: int) -> ChartOfAccount:
    account = db.get(ChartOfAccount, account_id)
    if not account or not account.is_active or not account.is_posting:
        raise HTTPException(422, "Adjustment account must be an active posting account")
    return account


def serialize(adjustment: SupplierAdjustment):
    invoice = adjustment.supplier_invoice
    return {
        "id": adjustment.id,
        "adjustment_number": adjustment.adjustment_number,
        "adjustment_type": adjustment.adjustment_type,
        "supplier_invoice_id": adjustment.supplier_invoice_id,
        "invoice_number": invoice.internal_invoice_number if invoice else None,
        "supplier_invoice_number": invoice.supplier_invoice_number if invoice else None,
        "supplier_id": adjustment.supplier_id,
        "supplier_name": adjustment.supplier.name if adjustment.supplier else None,
        "adjustment_date": adjustment.adjustment_date,
        "amount": adjustment.amount,
        "adjustment_account_id": adjustment.adjustment_account_id,
        "adjustment_account_code": adjustment.adjustment_account.account_number if adjustment.adjustment_account else None,
        "adjustment_account_name": adjustment.adjustment_account.account_name if adjustment.adjustment_account else None,
        "reason": adjustment.reason,
        "notes": adjustment.notes,
        "status": adjustment.status,
        "business_unit_id": adjustment.business_unit_id,
        "location_id": adjustment.location_id,
        "department_id": adjustment.department_id,
        "journal_entry_id": adjustment.journal_entry_id,
        "journal_number": adjustment.journal_entry.journal_number if adjustment.journal_entry else None,
        "created_by_name": adjustment.created_by.full_name if adjustment.created_by else None,
        "posted_by_name": adjustment.posted_by.full_name if adjustment.posted_by else None,
        "created_at": adjustment.created_at,
        "posted_at": adjustment.posted_at,
        "allowed_actions": {
            "can_edit": adjustment.status == "DRAFT",
            "can_post": adjustment.status == "DRAFT",
            "can_void": adjustment.status == "DRAFT",
            "can_print": True,
        },
    }


def validate_payload(db: Session, payload, adjustment: SupplierAdjustment | None = None):
    invoice_id = payload.supplier_invoice_id if hasattr(payload, "supplier_invoice_id") else adjustment.supplier_invoice_id
    invoice = db.get(SupplierInvoice, invoice_id)
    if not invoice:
        raise HTTPException(404, "Supplier invoice not found")
    if invoice.status != "POSTED":
        raise HTTPException(409, "Supplier adjustments require a posted supplier invoice")
    amount = payload.amount if payload.amount is not None else adjustment.amount
    remaining = Decimal(invoice.balance_amount)
    if adjustment and adjustment.status == "DRAFT":
        remaining = Decimal(invoice.balance_amount)
    if Decimal(amount) > remaining:
        raise HTTPException(409, f"Adjustment exceeds invoice outstanding balance {remaining}")
    account_id = payload.adjustment_account_id if payload.adjustment_account_id is not None else adjustment.adjustment_account_id
    validate_account(db, account_id)
    return invoice


@router.get("")
def listing(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    adjustment_type: str | None = None,
    status: str | None = None,
    supplier_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    access(user)
    query = db.query(SupplierAdjustment)
    if search:
        query = query.filter(or_(SupplierAdjustment.adjustment_number.ilike(f"%{search}%"), SupplierAdjustment.reason.ilike(f"%{search}%")))
    if adjustment_type:
        query = query.filter(SupplierAdjustment.adjustment_type == adjustment_type)
    if status:
        query = query.filter(SupplierAdjustment.status == status)
    if supplier_id:
        query = query.filter(SupplierAdjustment.supplier_id == supplier_id)
    if date_from:
        query = query.filter(SupplierAdjustment.adjustment_date >= date_from)
    if date_to:
        query = query.filter(SupplierAdjustment.adjustment_date <= date_to)
    total = query.count()
    rows = query.order_by(SupplierAdjustment.adjustment_date.desc(), SupplierAdjustment.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [serialize(row) for row in rows],
        "page": page,
        "page_size": page_size,
        "total_items": total,
        "total_pages": ceil(total / page_size) if total else 0,
        "has_next": page * page_size < total,
        "has_previous": page > 1,
    }


@router.post("", status_code=201)
def create(payload: SupplierAdjustmentCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    invoice = validate_payload(db, payload)
    prefix = "SCN" if payload.adjustment_type == "CREDIT_NOTE" else "SDN"
    adjustment = SupplierAdjustment(
        adjustment_number=next_document_number(db, prefix),
        adjustment_type=payload.adjustment_type,
        supplier_invoice_id=invoice.id,
        supplier_id=invoice.supplier_id,
        adjustment_date=payload.adjustment_date,
        amount=payload.amount,
        adjustment_account_id=payload.adjustment_account_id,
        reason=payload.reason,
        notes=payload.notes,
        status="DRAFT",
        business_unit_id=invoice.business_unit_id,
        location_id=invoice.location_id,
        department_id=invoice.department_id,
        created_by_id=user.id,
    )
    db.add(adjustment)
    db.flush()
    record_audit(db, user, "SUPPLIER_ADJUSTMENT_CREATED", "SUPPLIER_ADJUSTMENT", f"Created {adjustment.adjustment_number}", entity_id=adjustment.id, reference_document=invoice.internal_invoice_number)
    db.commit()
    db.refresh(adjustment)
    return serialize(adjustment)


@router.get("/{adjustment_id}")
def detail(adjustment_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    return serialize(get_adjustment(db, adjustment_id))


@router.patch("/{adjustment_id}")
def update(adjustment_id: int, payload: SupplierAdjustmentUpdate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    adjustment = get_adjustment(db, adjustment_id)
    if adjustment.status != "DRAFT":
        raise HTTPException(409, "Only draft supplier adjustments can be edited")
    validate_payload(db, payload, adjustment)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(adjustment, key, value)
    record_audit(db, user, "SUPPLIER_ADJUSTMENT_UPDATED", "SUPPLIER_ADJUSTMENT", f"Updated {adjustment.adjustment_number}", entity_id=adjustment.id)
    db.commit()
    db.refresh(adjustment)
    return serialize(adjustment)


@router.post("/{adjustment_id}/post")
def post(adjustment_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    adjustment = db.query(SupplierAdjustment).filter(SupplierAdjustment.id == adjustment_id).with_for_update().first()
    if not adjustment:
        raise HTTPException(404, "Supplier adjustment not found")
    if adjustment.status != "DRAFT":
        raise HTTPException(409, "Only draft supplier adjustments can be posted")
    invoice = db.query(SupplierInvoice).filter(SupplierInvoice.id == adjustment.supplier_invoice_id).with_for_update().one()
    if invoice.status != "POSTED":
        raise HTTPException(409, "Supplier invoice must remain posted")
    amount = Decimal(adjustment.amount)
    if amount > Decimal(invoice.balance_amount):
        raise HTTPException(409, "Adjustment exceeds current invoice outstanding balance")

    rule = db.query(AccountingPostingRule).filter(AccountingPostingRule.event_type == "SUPPLIER_PAYMENT", AccountingPostingRule.is_active.is_(True)).first()
    if not rule:
        raise HTTPException(409, "No active SUPPLIER_PAYMENT posting rule configured for Accounts Payable")
    payable_account = db.get(ChartOfAccount, rule.debit_account_id)
    adjustment_account = validate_account(db, adjustment.adjustment_account_id)
    if not payable_account or not payable_account.is_active or not payable_account.is_posting:
        raise HTTPException(409, "Accounts Payable posting account is invalid")
    if payable_account.id == adjustment_account.id:
        raise HTTPException(422, "Adjustment account must differ from Accounts Payable")

    now = datetime.now(timezone.utc)
    journal = JournalEntry(
        journal_number=next_document_number(db, "JV"),
        posting_date=adjustment.adjustment_date,
        status="POSTED",
        document_type=adjustment.adjustment_type,
        document_number=adjustment.adjustment_number,
        reference_type="SUPPLIER_ADJUSTMENT",
        reference_id=adjustment.id,
        description=f"{adjustment.adjustment_type.replace('_', ' ').title()} {adjustment.adjustment_number}: {adjustment.reason}",
        created_by_id=user.id,
        posted_by_id=user.id,
        posted_at=now,
        business_unit_id=adjustment.business_unit_id,
        location_id=adjustment.location_id,
        department_id=adjustment.department_id,
    )
    journal.lines = [
        JournalLine(line_number=1, account_id=payable_account.id, debit=amount, credit=ZERO, description=adjustment.reason, supplier_id=adjustment.supplier_id, business_unit_id=adjustment.business_unit_id, location_id=adjustment.location_id, department_id=adjustment.department_id),
        JournalLine(line_number=2, account_id=adjustment_account.id, debit=ZERO, credit=amount, description=adjustment.reason, supplier_id=adjustment.supplier_id, business_unit_id=adjustment.business_unit_id, location_id=adjustment.location_id, department_id=adjustment.department_id),
    ]
    db.add(journal)
    db.flush()
    for line in journal.lines:
        GeneralLedgerService.post(
            db=db,
            account_id=line.account_id,
            debit=line.debit,
            credit=line.credit,
            posting_date=journal.posting_date,
            journal_source="SUPPLIER_ADJUSTMENT",
            document_type=journal.document_type,
            document_number=journal.document_number,
            reference_type=journal.reference_type,
            reference_id=journal.reference_id,
            reference_number=journal.journal_number,
            description=line.description,
            user_id=user.id,
        )

    invoice.adjustment_amount = Decimal(invoice.adjustment_amount or 0) + amount
    invoice.balance_amount = Decimal(invoice.total_amount) - Decimal(invoice.paid_amount or 0) - Decimal(invoice.adjustment_amount)
    invoice.payment_status = "PAID" if invoice.balance_amount == ZERO else "PARTIALLY_PAID"
    payable = db.query(AccountPayable).filter(AccountPayable.supplier_id == invoice.supplier_id, AccountPayable.invoice_number == invoice.internal_invoice_number).first()
    if payable:
        payable.outstanding_amount = invoice.balance_amount
        payable.payment_status = invoice.payment_status
        payable.status = "PAID" if invoice.balance_amount == ZERO else "OPEN"

    adjustment.status = "POSTED"
    adjustment.journal_entry_id = journal.id
    adjustment.posted_by_id = user.id
    adjustment.posted_at = now
    record_audit(db, user, "SUPPLIER_ADJUSTMENT_POSTED", "SUPPLIER_ADJUSTMENT", f"Posted {adjustment.adjustment_number}", entity_id=adjustment.id, reference_document=journal.journal_number)
    db.commit()
    db.refresh(adjustment)
    return serialize(adjustment)


@router.post("/{adjustment_id}/void")
def void(adjustment_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    adjustment = get_adjustment(db, adjustment_id)
    if adjustment.status != "DRAFT":
        raise HTTPException(409, "Posted supplier adjustments require reversal and cannot be voided")
    adjustment.status = "VOID"
    adjustment.voided_at = datetime.now(timezone.utc)
    record_audit(db, user, "SUPPLIER_ADJUSTMENT_VOIDED", "SUPPLIER_ADJUSTMENT", f"Voided {adjustment.adjustment_number}", entity_id=adjustment.id)
    db.commit()
    db.refresh(adjustment)
    return serialize(adjustment)
