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


def unpost_journal(db: Session, *, journal: JournalEntry, user) -> JournalEntry:
    if journal.status != "POSTED":
        raise HTTPException(status_code=409, detail="Only posted journals can be unposted")

    source = (journal.reference_type or "MANUAL").upper()
    if source not in SUPPORTED_SOURCE_TYPES:
        raise HTTPException(
            status_code=409,
            detail=f"Journal source {source} does not yet have a safe unpost handler. Reverse it from its originating module.",
        )

    # The accounting period remains the hard lock. Administrators can reopen the
    # fiscal period first, then unpost/rework the source document.
    FiscalPeriodService.validate_posting_date(db=db, posting_date=journal.posting_date)

    gl_rows = db.query(GeneralLedger).filter(
        GeneralLedger.reference_number == journal.journal_number,
        GeneralLedger.reference_type == journal.reference_type,
        GeneralLedger.reference_id == journal.reference_id,
    ).all()
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
    db.commit()
    db.refresh(journal)
    return journal
