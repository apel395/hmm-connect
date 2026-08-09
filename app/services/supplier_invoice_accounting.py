from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.journal_entry import JournalEntry
from app.models.payment import Payment, PaymentAllocation
from app.models.supplier_invoice import SupplierInvoice

ZERO = Decimal("0")


def invoice_journals(db: Session, invoice_id: int):
    return (
        db.query(JournalEntry)
        .filter(
            JournalEntry.reference_type == "SUPPLIER_INVOICE",
            JournalEntry.reference_id == invoice_id,
        )
        .order_by(JournalEntry.id.desc())
        .all()
    )


def posting_status(db: Session, invoice_id: int) -> str:
    journals = invoice_journals(db, invoice_id)
    if any(journal.status == "POSTED" for journal in journals):
        return "POSTED"
    if any(journal.status == "DRAFT" for journal in journals):
        return "UNPOSTED"
    if journals and all(journal.status == "VOID" for journal in journals):
        return "VOID"
    return "UNPOSTED"


def document_status(invoice: SupplierInvoice) -> str:
    # Legacy SupplierInvoice.status used POSTED as both a document and accounting state.
    # The normalized API keeps verification separate; posting_status owns accounting state.
    return "VERIFIED" if invoice.status == "POSTED" else invoice.status


def has_posted_invoice_journal(db: Session, invoice_id: int) -> bool:
    return (
        db.query(JournalEntry.id)
        .filter(
            JournalEntry.reference_type == "SUPPLIER_INVOICE",
            JournalEntry.reference_id == invoice_id,
            JournalEntry.status == "POSTED",
        )
        .first()
        is not None
    )


def posted_payment_total(db: Session, invoice_id: int) -> Decimal:
    rows = (
        db.query(PaymentAllocation.allocated_amount)
        .join(Payment, Payment.id == PaymentAllocation.payment_id)
        .filter(
            PaymentAllocation.supplier_invoice_id == invoice_id,
            Payment.status == "POSTED",
        )
        .all()
    )
    return sum((Decimal(amount or 0) for (amount,) in rows), ZERO)


def accounting_state(db: Session, invoice: SupplierInvoice) -> dict:
    posting = posting_status(db, invoice.id)
    document = document_status(invoice)
    posted_payments = posted_payment_total(db, invoice.id)
    exceptions: list[str] = []

    if posted_payments > ZERO and posting != "POSTED":
        exceptions.append("PAYMENT_POSTED_BEFORE_INVOICE_JOURNAL")
    if invoice.status == "POSTED" and posting != "POSTED":
        exceptions.append("DOCUMENT_POSTED_WITHOUT_POSTED_JOURNAL")
    if posting == "POSTED" and document in {"DRAFT", "REJECTED", "VOID"}:
        exceptions.append("POSTED_JOURNAL_WITH_INVALID_DOCUMENT_STATE")

    return {
        "document_status": document,
        "posting_status": posting,
        "payment_status": invoice.payment_status,
        "balance_amount": Decimal(invoice.balance_amount or 0),
        "posted_payment_amount": posted_payments,
        "accounting_exception": bool(exceptions),
        "accounting_exception_codes": exceptions,
    }
