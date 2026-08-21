from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.account_payable import AccountPayable
from app.models.bank_transfer import BankTransfer
from app.models.general_ledger import GeneralLedger
from app.models.journal_entry import JournalEntry
from app.models.payment import Payment, PaymentAllocation
from app.models.supplier_adjustment import SupplierAdjustment
from app.models.supplier_invoice import SupplierInvoice
from app.services.audit import record_audit
from app.services.fiscal_period_service import FiscalPeriodService
from app.services.general_ledger import GeneralLedgerService

ZERO = Decimal("0")
SUPPORTED_SOURCE_TYPES = {
    "MANUAL",
    "SUPPLIER_INVOICE",
    "SUPPLIER_PAYMENT",
    "SUPPLIER_ADJUSTMENT",
    "BANK_TRANSFER",
}


def _invoice_balance(invoice: SupplierInvoice) -> Decimal:
    return max(
        ZERO,
        Decimal(invoice.total_amount or 0)
        - Decimal(invoice.paid_amount or 0)
        - Decimal(invoice.adjustment_amount or 0),
    )


def _sync_invoice_payable(db: Session, invoice: SupplierInvoice) -> None:
    balance = _invoice_balance(invoice)
    invoice.balance_amount = balance
    paid_or_adjusted = Decimal(invoice.paid_amount or 0) > ZERO or Decimal(invoice.adjustment_amount or 0) > ZERO
    invoice.payment_status = "PAID" if balance == ZERO else "PARTIALLY_PAID" if paid_or_adjusted else "UNPAID"

    payable = db.query(AccountPayable).filter(
        AccountPayable.supplier_id == invoice.supplier_id,
        AccountPayable.invoice_number == invoice.internal_invoice_number,
    ).first()
    if not payable:
        return
    payable.amount = invoice.total_amount
    payable.paid_amount = invoice.paid_amount
    payable.outstanding_amount = balance
    payable.payment_status = invoice.payment_status
    payable.status = "PAID" if balance == ZERO else "OPEN"
    payable.last_payment_date = db.query(func.max(Payment.payment_date)).join(
        PaymentAllocation,
        PaymentAllocation.payment_id == Payment.id,
    ).filter(
        PaymentAllocation.supplier_invoice_id == invoice.id,
        Payment.status == "POSTED",
    ).scalar()


def _assert_invoice_has_no_posted_dependents(db: Session, invoice: SupplierInvoice) -> None:
    posted_payment = db.query(PaymentAllocation).join(Payment).filter(
        PaymentAllocation.supplier_invoice_id == invoice.id,
        Payment.status == "POSTED",
    ).first()
    if posted_payment:
        raise HTTPException(
            status_code=409,
            detail="Supplier invoice has a posted payment. Unpost the payment journal first.",
        )
    posted_adjustment = db.query(SupplierAdjustment).filter(
        SupplierAdjustment.supplier_invoice_id == invoice.id,
        SupplierAdjustment.status == "POSTED",
    ).first()
    if posted_adjustment:
        raise HTTPException(
            status_code=409,
            detail="Supplier invoice has a posted credit/debit note. Unpost the adjustment journal first.",
        )


def apply_source_post_state(db: Session, *, journal: JournalEntry, user) -> None:
    """Reapply the originating document state before a previously-unposted journal commits.

    The journal/GL is the accounting lock. This keeps the operational document in sync
    when an administrator unposts, corrects, and reposts from the Journal workspace.
    """
    source = (journal.reference_type or "MANUAL").upper()
    now = datetime.now(timezone.utc)

    if source == "MANUAL":
        return

    if source == "SUPPLIER_INVOICE":
        invoice = db.get(SupplierInvoice, journal.reference_id)
        if not invoice:
            raise HTTPException(409, "Supplier invoice linked to this journal was not found")
        if invoice.status not in {"VERIFIED", "POSTED"}:
            raise HTTPException(409, "Supplier invoice must be verified before its journal can be posted")
        invoice.status = "POSTED"
        invoice.posted_at = now
        return

    if source == "SUPPLIER_PAYMENT":
        payment = db.get(Payment, journal.reference_id)
        if not payment:
            raise HTTPException(409, "Supplier payment linked to this journal was not found")
        if payment.status != "APPROVED":
            raise HTTPException(409, "Supplier payment must be approved before its journal can be posted")
        for allocation in payment.allocations:
            invoice = db.query(SupplierInvoice).filter(
                SupplierInvoice.id == allocation.supplier_invoice_id,
            ).with_for_update().one()
            if invoice.status != "POSTED":
                raise HTTPException(409, f"Invoice {invoice.internal_invoice_number} must remain posted")
            amount = Decimal(allocation.allocated_amount or 0)
            current_balance = _invoice_balance(invoice)
            if amount <= ZERO or amount > current_balance:
                raise HTTPException(409, f"Payment allocation is no longer valid for {invoice.internal_invoice_number}")
            invoice.paid_amount = Decimal(invoice.paid_amount or 0) + amount
            _sync_invoice_payable(db, invoice)
        payment.status = "POSTED"
        payment.posted_by_id = user.id
        payment.posted_at = now
        return

    if source == "SUPPLIER_ADJUSTMENT":
        adjustment = db.get(SupplierAdjustment, journal.reference_id)
        if not adjustment:
            raise HTTPException(409, "Supplier adjustment linked to this journal was not found")
        if adjustment.status != "DRAFT":
            raise HTTPException(409, "Supplier adjustment must be draft before its journal can be reposted")
        invoice = db.query(SupplierInvoice).filter(
            SupplierInvoice.id == adjustment.supplier_invoice_id,
        ).with_for_update().one()
        if invoice.status != "POSTED":
            raise HTTPException(409, "Supplier invoice must remain posted")
        amount = Decimal(adjustment.amount or 0)
        if amount <= ZERO or amount > _invoice_balance(invoice):
            raise HTTPException(409, "Supplier adjustment exceeds the current invoice balance")
        invoice.adjustment_amount = Decimal(invoice.adjustment_amount or 0) + amount
        _sync_invoice_payable(db, invoice)
        adjustment.status = "POSTED"
        adjustment.posted_by_id = user.id
        adjustment.posted_at = now
        return

    if source == "BANK_TRANSFER":
        transfer = db.get(BankTransfer, journal.reference_id)
        if not transfer:
            raise HTTPException(409, "Bank transfer linked to this journal was not found")
        if transfer.status != "DRAFT":
            raise HTTPException(409, "Bank transfer must be draft before its journal can be reposted")
        transfer.status = "POSTED"
        transfer.posted_by_id = user.id
        transfer.posted_at = now
        return

    raise HTTPException(
        status_code=409,
        detail=f"Journal source {source} does not yet have a safe repost handler.",
    )


def _reverse_source_state(db: Session, journal: JournalEntry) -> None:
    source = (journal.reference_type or "MANUAL").upper()

    if source == "MANUAL":
        return

    if source == "SUPPLIER_INVOICE":
        invoice = db.get(SupplierInvoice, journal.reference_id)
        if not invoice:
            raise HTTPException(status_code=409, detail="Supplier invoice linked to this journal was not found")
        _assert_invoice_has_no_posted_dependents(db, invoice)
        invoice.status = "VERIFIED"
        invoice.posted_at = None
        return

    if source == "SUPPLIER_PAYMENT":
        payment = db.get(Payment, journal.reference_id)
        if not payment:
            raise HTTPException(status_code=409, detail="Supplier payment linked to this journal was not found")
        if payment.status != "POSTED":
            raise HTTPException(status_code=409, detail="Linked supplier payment is not posted")
        for allocation in payment.allocations:
            invoice = db.query(SupplierInvoice).filter(
                SupplierInvoice.id == allocation.supplier_invoice_id,
            ).with_for_update().one()
            invoice.paid_amount = max(
                ZERO,
                Decimal(invoice.paid_amount or 0) - Decimal(allocation.allocated_amount or 0),
            )
            _sync_invoice_payable(db, invoice)
        payment.status = "APPROVED"
        payment.posted_by_id = None
        payment.posted_at = None
        return

    if source == "SUPPLIER_ADJUSTMENT":
        adjustment = db.get(SupplierAdjustment, journal.reference_id)
        if not adjustment:
            raise HTTPException(status_code=409, detail="Supplier adjustment linked to this journal was not found")
        if adjustment.status != "POSTED":
            raise HTTPException(status_code=409, detail="Linked supplier adjustment is not posted")
        invoice = db.query(SupplierInvoice).filter(
            SupplierInvoice.id == adjustment.supplier_invoice_id,
        ).with_for_update().one()
        invoice.adjustment_amount = max(
            ZERO,
            Decimal(invoice.adjustment_amount or 0) - Decimal(adjustment.amount or 0),
        )
        _sync_invoice_payable(db, invoice)
        adjustment.status = "DRAFT"
        adjustment.posted_by_id = None
        adjustment.posted_at = None
        return

    if source == "BANK_TRANSFER":
        transfer = db.get(BankTransfer, journal.reference_id)
        if not transfer:
            raise HTTPException(status_code=409, detail="Bank transfer linked to this journal was not found")
        transfer.status = "DRAFT"
        transfer.posted_by_id = None
        transfer.posted_at = None
        return

    raise HTTPException(
        status_code=409,
        detail=f"Journal source {source} does not yet have a safe unpost handler. Reverse it from its originating module.",
    )


def matching_ledger_rows(db: Session, journal: JournalEntry) -> list[GeneralLedger]:
    return db.query(GeneralLedger).filter(
        GeneralLedger.reference_number == journal.journal_number,
        GeneralLedger.reference_type == journal.reference_type,
        GeneralLedger.reference_id == journal.reference_id,
    ).all()


def recreate_journal_ledger(
    db: Session,
    *,
    journal: JournalEntry,
    user,
) -> int:
    """Replace persisted GL rows for a posted journal without changing its source state."""
    if journal.status != "POSTED":
        raise HTTPException(status_code=409, detail="Only posted journals can be recreated")
    if not journal.lines:
        raise HTTPException(status_code=409, detail="Journal has no lines to recreate")

    FiscalPeriodService.validate_posting_date(db=db, posting_date=journal.posting_date)
    previous_rows = matching_ledger_rows(db, journal)
    for row in previous_rows:
        db.delete(row)
    db.flush()

    for line in journal.lines:
        GeneralLedgerService.post(
            db=db,
            account_id=line.account_id,
            debit=line.debit,
            credit=line.credit,
            posting_date=journal.posting_date,
            journal_source=journal.reference_type,
            document_type=journal.document_type,
            document_number=journal.document_number,
            reference_type=journal.reference_type,
            reference_id=journal.reference_id,
            reference_number=journal.journal_number,
            description=line.description,
            user_id=user.id,
        )

    record_audit(
        db,
        user,
        "JOURNAL_LEDGER_RECREATED",
        "JOURNAL_ENTRY",
        f"Recreated ledger rows for {journal.journal_number}",
        entity_id=journal.id,
        reference_document=journal.document_number,
        before_data={"ledger_row_count": len(previous_rows)},
        after_data={"ledger_row_count": len(journal.lines)},
    )
    return len(journal.lines)


def unpost_journal(
    db: Session,
    *,
    journal: JournalEntry,
    user,
    commit: bool = True,
) -> JournalEntry:
    if journal.status != "POSTED":
        raise HTTPException(status_code=409, detail="Only posted journals can be unposted")

    source = (journal.reference_type or "MANUAL").upper()
    if source not in SUPPORTED_SOURCE_TYPES:
        raise HTTPException(
            status_code=409,
            detail=f"Journal source {source} does not yet have a safe unpost handler. Reverse it from its originating module.",
        )

    # Fiscal period remains the hard accounting lock. Admin can reopen the period,
    # then unpost/rework the document. We never silently bypass a closed period.
    FiscalPeriodService.validate_posting_date(db=db, posting_date=journal.posting_date)

    gl_rows = matching_ledger_rows(db, journal)
    if not gl_rows:
        raise HTTPException(status_code=409, detail="Journal has no matching ledger rows to unpost")

    _reverse_source_state(db, journal)
    for row in gl_rows:
        db.delete(row)

    previous_posted_at = journal.posted_at
    journal.status = "DRAFT"
    journal.posted_by_id = None
    journal.posted_at = None

    record_audit(
        db,
        user,
        "JOURNAL_UNPOSTED",
        "JOURNAL_ENTRY",
        f"Unposted {journal.journal_number}",
        entity_id=journal.id,
        reference_document=journal.document_number,
        before_data={
            "status": "POSTED",
            "posted_at": str(previous_posted_at) if previous_posted_at else None,
            "source": source,
        },
        after_data={"status": "DRAFT", "source": source},
    )
    if commit:
        db.commit()
        db.refresh(journal)
    else:
        db.flush()
    return journal
