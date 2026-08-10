from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import is_superuser
from app.models.journal_entry import JournalEntry
from app.models.payment import Payment, PaymentAllocation
from app.models.supplier_adjustment import SupplierAdjustment
from app.models.supplier_invoice import SupplierInvoice
from app.models.bank_transfer import BankTransfer
from app.services.accounting_unpost import unpost_journal
from app.services.audit import record_audit

router = APIRouter(tags=["Administrator Lifecycle Overrides"])


def require_admin(user) -> None:
    if not is_superuser(user):
        raise HTTPException(status_code=403, detail="Administrator access required")


def source_journal(db: Session, source: str, source_id: int, *, status: str | None = None) -> JournalEntry | None:
    query = db.query(JournalEntry).filter(
        JournalEntry.reference_type == source,
        JournalEntry.reference_id == source_id,
    )
    if status:
        query = query.filter(JournalEntry.status == status)
    else:
        query = query.filter(JournalEntry.status != "VOID")
    return query.order_by(JournalEntry.id.desc()).first()


def unpost_source(db: Session, *, source: str, source_id: int, user):
    require_admin(user)
    journal = source_journal(db, source, source_id, status="POSTED")
    if not journal:
        raise HTTPException(status_code=409, detail="No posted journal exists for this document")
    return unpost_journal(db, journal=journal, user=user)


@router.post("/supplier-invoices/{invoice_id}/unpost")
def unpost_supplier_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    invoice = db.get(SupplierInvoice, invoice_id)
    if not invoice:
        raise HTTPException(404, "Supplier invoice not found")
    journal = unpost_source(db, source="SUPPLIER_INVOICE", source_id=invoice.id, user=user)
    return {"id": invoice.id, "status": db.get(SupplierInvoice, invoice.id).status, "journal_entry_id": journal.id, "journal_status": journal.status}


@router.post("/supplier-invoices/{invoice_id}/reopen")
def reopen_supplier_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    require_admin(user)
    invoice = db.query(SupplierInvoice).filter(SupplierInvoice.id == invoice_id).with_for_update().first()
    if not invoice:
        raise HTTPException(404, "Supplier invoice not found")
    if invoice.status == "POSTED":
        raise HTTPException(409, "Unpost the supplier invoice journal before reopening the invoice")
    if invoice.status == "DRAFT":
        raise HTTPException(409, "Supplier invoice is already draft")

    blocking_payment = db.query(PaymentAllocation).join(Payment).filter(
        PaymentAllocation.supplier_invoice_id == invoice.id,
        Payment.status.in_(["APPROVED", "POSTED"]),
    ).first()
    if blocking_payment:
        raise HTTPException(409, "Supplier invoice has an approved/posted payment. Unpost and reopen that payment first.")
    blocking_adjustment = db.query(SupplierAdjustment).filter(
        SupplierAdjustment.supplier_invoice_id == invoice.id,
        SupplierAdjustment.status.in_(["DRAFT", "POSTED"]),
    ).first()
    if blocking_adjustment:
        raise HTTPException(409, "Supplier invoice has an active credit/debit note. Void/unpost that adjustment first.")

    journal = source_journal(db, "SUPPLIER_INVOICE", invoice.id)
    if journal and journal.status == "DRAFT":
        journal.status = "VOID"
        journal.voided_at = datetime.now(timezone.utc)

    previous = invoice.status
    invoice.status = "DRAFT"
    invoice.verified_at = None
    invoice.posted_at = None
    invoice.voided_at = None
    record_audit(
        db,
        user,
        "SUPPLIER_INVOICE_REOPENED",
        "SUPPLIER_INVOICE",
        f"Reopened {invoice.internal_invoice_number} for correction",
        entity_id=invoice.id,
        before_data={"status": previous},
        after_data={"status": "DRAFT", "admin_override": True},
    )
    db.commit()
    return {"id": invoice.id, "status": invoice.status}


@router.post("/payments/{payment_id}/unpost")
def unpost_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    payment = db.get(Payment, payment_id)
    if not payment:
        raise HTTPException(404, "Payment not found")
    journal = unpost_source(db, source="SUPPLIER_PAYMENT", source_id=payment.id, user=user)
    return {"id": payment.id, "status": db.get(Payment, payment.id).status, "journal_entry_id": journal.id, "journal_status": journal.status}


@router.post("/payments/{payment_id}/reopen")
def reopen_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    require_admin(user)
    payment = db.query(Payment).filter(Payment.id == payment_id).with_for_update().first()
    if not payment:
        raise HTTPException(404, "Payment not found")
    if payment.status == "POSTED":
        raise HTTPException(409, "Unpost the payment journal before reopening the payment")
    if payment.status == "DRAFT":
        raise HTTPException(409, "Payment is already draft")
    if payment.status not in {"APPROVED", "VOID"}:
        raise HTTPException(409, f"Payment status {payment.status} cannot be reopened")

    journal = source_journal(db, "SUPPLIER_PAYMENT", payment.id)
    if journal and journal.status == "DRAFT":
        journal.status = "VOID"
        journal.voided_at = datetime.now(timezone.utc)
    payment.journal_entry_id = None
    previous = payment.status
    payment.status = "DRAFT"
    payment.approved_by_id = None
    payment.approved_at = None
    payment.posted_by_id = None
    payment.posted_at = None
    payment.voided_at = None
    record_audit(
        db,
        user,
        "PAYMENT_REOPENED",
        "PAYMENT",
        f"Reopened {payment.payment_number} for correction",
        entity_id=payment.id,
        before_data={"status": previous},
        after_data={"status": "DRAFT", "admin_override": True},
    )
    db.commit()
    return {"id": payment.id, "status": payment.status}


@router.post("/supplier-adjustments/{adjustment_id}/unpost")
def unpost_supplier_adjustment(
    adjustment_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    adjustment = db.get(SupplierAdjustment, adjustment_id)
    if not adjustment:
        raise HTTPException(404, "Supplier adjustment not found")
    journal = unpost_source(db, source="SUPPLIER_ADJUSTMENT", source_id=adjustment.id, user=user)
    return {"id": adjustment.id, "status": db.get(SupplierAdjustment, adjustment.id).status, "journal_entry_id": journal.id, "journal_status": journal.status}


@router.post("/bank-transfers/{transfer_id}/unpost")
def unpost_bank_transfer(
    transfer_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    transfer = db.get(BankTransfer, transfer_id)
    if not transfer:
        raise HTTPException(404, "Bank transfer not found")
    journal = unpost_source(db, source="BANK_TRANSFER", source_id=transfer.id, user=user)
    return {"id": transfer.id, "status": db.get(BankTransfer, transfer.id).status, "journal_entry_id": journal.id, "journal_status": journal.status}
