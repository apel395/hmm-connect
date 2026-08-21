from datetime import date, datetime, timezone
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_any_role
from app.models.journal_entry import JournalEntry
from app.models.supplier_invoice import SupplierInvoice
from app.schemas.supplier_invoice import SupplierInvoiceInput
from app.services.audit import record_audit
from app.services.document_context import document_context, print_metadata
from app.services.supplier_invoice_runtime_service import SupplierInvoiceService
from app.services.location_access import apply_location_scope, enforce_location_access, resolve_location_id

router = APIRouter(prefix="/supplier-invoices", tags=["Supplier Invoices"])


def access(user):
    if not has_any_role(user, "FINANCE"):
        raise HTTPException(403, "Finance access required")


def get(db, invoice_id, user):
    invoice = db.get(SupplierInvoice, invoice_id)
    if not invoice:
        raise HTTPException(404, "Supplier invoice not found")
    enforce_location_access(user, invoice.location_id)
    return invoice


def result(db, invoice, user):
    service = SupplierInvoiceService(db)
    data = service.serialize(service.attach_journal(invoice))
    match = service.match_summary(invoice)
    data["three_way_match"] = match
    data.update(document_context(db, "SUPPLIER_INVOICE", invoice.id, invoice.status, user))
    data["allowed_actions"] = {
        "can_edit": invoice.status == "DRAFT",
        "can_verify": invoice.status == "DRAFT" and match["can_verify"],
        "can_reject": invoice.status in {"DRAFT", "VERIFIED"} and not data["related_journal"],
        "can_generate_journal": invoice.status == "VERIFIED" and not data["related_journal"],
        "can_void": invoice.status in {"DRAFT", "VERIFIED"},
        "can_print": True,
        "can_manage_attachments": True,
        "can_view_history": True,
    }
    return data


@router.get("")
def listing(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    supplier_id: int | None = None,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    due_from: date | None = None,
    due_to: date | None = None,
    po_number: str | None = None,
    receipt_number: str | None = None,
    source_type: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    access(user)
    query = apply_location_scope(db.query(SupplierInvoice), SupplierInvoice, user)
    if search:
        query = query.filter(or_(SupplierInvoice.internal_invoice_number.ilike(f"%{search}%"), SupplierInvoice.supplier_invoice_number.ilike(f"%{search}%")))
    if supplier_id:
        query = query.filter(SupplierInvoice.supplier_id == supplier_id)
    if status:
        query = query.filter(SupplierInvoice.status == status)
    if date_from:
        query = query.filter(SupplierInvoice.invoice_date >= date_from)
    if date_to:
        query = query.filter(SupplierInvoice.invoice_date <= date_to)
    if due_from:
        query = query.filter(SupplierInvoice.due_date >= due_from)
    if due_to:
        query = query.filter(SupplierInvoice.due_date <= due_to)
    if po_number:
        query = query.join(SupplierInvoice.purchase_order).filter_by(po_number=po_number)
    if receipt_number:
        query = query.join(SupplierInvoice.goods_receipt).filter_by(receipt_number=receipt_number)
    if source_type:
        query = query.filter(SupplierInvoice.source_type == source_type)
    total = query.count()
    rows = query.order_by(SupplierInvoice.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    service = SupplierInvoiceService(db)
    return {
        "items": [service.serialize(service.attach_journal(item)) for item in rows],
        "page": page,
        "page_size": page_size,
        "total_items": total,
        "total_pages": ceil(total / page_size) if total else 0,
        "has_next": page * page_size < total,
        "has_previous": page > 1,
    }


@router.get("/{invoice_id}")
def detail(invoice_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    return result(db, get(db, invoice_id, user), user)


@router.post("", status_code=201)
def create(data: SupplierInvoiceInput, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    data.location_id = resolve_location_id(user, data.location_id)
    return result(db, SupplierInvoiceService(db).create(data, user), user)


@router.patch("/{invoice_id}")
def update(invoice_id: int, data: SupplierInvoiceInput, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    data.location_id = resolve_location_id(user, data.location_id)
    return result(db, SupplierInvoiceService(db).update(get(db, invoice_id, user), data, user), user)


@router.post("/{invoice_id}/verify")
def verify(invoice_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Verify the invoice and prepare accounting, but never post the journal here."""
    access(user)
    service = SupplierInvoiceService(db)
    invoice = service.verify(get(db, invoice_id, user), user)
    try:
        service.generate_journal(invoice, user)
    except HTTPException as exc:
        db.rollback()
        data = result(db, get(db, invoice_id, user), user)
        data["accounting_warning"] = exc.detail
        return data
    return result(db, get(db, invoice_id, user), user)


@router.post("/{invoice_id}/reject")
def reject(invoice_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    invoice = get(db, invoice_id, user)
    if invoice.status not in {"DRAFT", "VERIFIED"}:
        raise HTTPException(409, "Only draft or verified invoices without a journal can be rejected")
    journal = db.query(JournalEntry).filter(
        JournalEntry.reference_type == "SUPPLIER_INVOICE",
        JournalEntry.reference_id == invoice.id,
        JournalEntry.status != "VOID",
    ).first()
    if journal:
        raise HTTPException(409, "Invoice with a journal cannot be rejected")
    previous = invoice.status
    invoice.status = "REJECTED"
    record_audit(
        db, user, "SUPPLIER_INVOICE_REJECTED", "SUPPLIER_INVOICE",
        f"Rejected {invoice.internal_invoice_number}", entity_id=invoice.id,
        before_data={"status": previous}, after_data={"status": "REJECTED"},
    )
    db.commit()
    db.refresh(invoice)
    return result(db, invoice, user)


@router.post("/{invoice_id}/generate-journal")
def generate(invoice_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    invoice = get(db, invoice_id, user)
    existing = db.query(JournalEntry).filter(
        JournalEntry.reference_type == "SUPPLIER_INVOICE",
        JournalEntry.reference_id == invoice.id,
        JournalEntry.status != "VOID",
    ).first()
    if existing:
        return {"id": existing.id, "journal_number": existing.journal_number, "status": existing.status}
    journal = SupplierInvoiceService(db).generate_journal(invoice, user)
    return {"id": journal.id, "journal_number": journal.journal_number, "status": journal.status}


@router.post("/{invoice_id}/void")
def void(invoice_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    invoice = get(db, invoice_id, user)
    if invoice.status == "POSTED":
        raise HTTPException(409, "Posted invoices cannot be voided without a reversal")
    if invoice.status == "VOID":
        raise HTTPException(409, "Invoice is already void")
    now = datetime.now(timezone.utc)
    invoice.status = "VOID"
    invoice.voided_at = now
    journal = db.query(JournalEntry).filter(
        JournalEntry.reference_type == "SUPPLIER_INVOICE",
        JournalEntry.reference_id == invoice.id,
        JournalEntry.status == "DRAFT",
    ).first()
    if journal:
        journal.status = "VOID"
        journal.voided_at = now
        record_audit(db, user, "JOURNAL_VOIDED", "JOURNAL_ENTRY", f"Voided {journal.journal_number}", entity_id=journal.id, reference_document=invoice.internal_invoice_number)
    record_audit(db, user, "SUPPLIER_INVOICE_VOIDED", "SUPPLIER_INVOICE", f"Voided {invoice.internal_invoice_number}", entity_id=invoice.id)
    db.commit()
    db.refresh(invoice)
    return result(db, invoice, user)


@router.get("/{invoice_id}/allowed-actions")
def actions(invoice_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    return result(db, get(db, invoice_id, user), user)["allowed_actions"]


@router.get("/{invoice_id}/print")
def printable(invoice_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    return {**result(db, get(db, invoice_id, user), user), "document_type": "Supplier Invoice", **print_metadata(user)}
