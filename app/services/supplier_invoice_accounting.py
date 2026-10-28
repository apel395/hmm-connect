from app.services.journal_recognition import recognized_journal_filter
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.account_payable import AccountPayable
from app.models.journal_entry import JournalEntry
from app.models.payment import Payment, PaymentAllocation
from app.models.supplier_invoice import SupplierInvoice
from app.services.payable_balance import invoice_balance

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


def payable_mirror(db: Session, invoice: SupplierInvoice) -> AccountPayable | None:
    return (
        db.query(AccountPayable)
        .filter(
            AccountPayable.supplier_id == invoice.supplier_id,
            AccountPayable.invoice_number == invoice.internal_invoice_number,
        )
        .first()
    )


def accounting_state(db: Session, invoice: SupplierInvoice) -> dict:
    posting = posting_status(db, invoice.id)
    recognized = bool(db.query(JournalEntry.id).filter(JournalEntry.reference_type=="SUPPLIER_INVOICE",JournalEntry.reference_id==invoice.id,recognized_journal_filter()).first())
    document = document_status(invoice)
    posted_payments = posted_payment_total(db, invoice.id)
    authoritative_balance = invoice_balance(invoice)
    payable = payable_mirror(db, invoice)
    exceptions: list[str] = []

    if posted_payments > ZERO and not recognized:
        exceptions.append("PAYMENT_POSTED_BEFORE_INVOICE_JOURNAL")
    if invoice.status == "POSTED" and not recognized:
        exceptions.append("DOCUMENT_POSTED_WITHOUT_POSTED_JOURNAL")
    if posting == "POSTED" and document in {"DRAFT", "REJECTED", "VOID"}:
        exceptions.append("POSTED_JOURNAL_WITH_INVALID_DOCUMENT_STATE")
    if Decimal(invoice.balance_amount or 0) != authoritative_balance:
        exceptions.append("INVOICE_BALANCE_DRIFT")
    if Decimal(invoice.paid_amount or 0) != posted_payments:
        exceptions.append("INVOICE_PAID_AMOUNT_DIFFERS_FROM_POSTED_PAYMENTS")

    if document in {"VERIFIED"} or posting == "POSTED":
        if payable is None:
            exceptions.append("ACCOUNT_PAYABLE_MIRROR_MISSING")
        else:
            if Decimal(payable.amount or 0) != Decimal(invoice.total_amount or 0):
                exceptions.append("AP_TOTAL_MISMATCH")
            if Decimal(payable.paid_amount or 0) != Decimal(invoice.paid_amount or 0):
                exceptions.append("AP_PAID_MISMATCH")
            if Decimal(payable.outstanding_amount or 0) != authoritative_balance:
                exceptions.append("AP_OUTSTANDING_MISMATCH")
            if payable.payment_status != invoice.payment_status:
                exceptions.append("AP_PAYMENT_STATUS_MISMATCH")

    return {
        "document_status": document,
        "posting_status": posting,
        "accounting_recognized": recognized,
        "payment_status": invoice.payment_status,
        "balance_amount": authoritative_balance,
        "stored_balance_amount": Decimal(invoice.balance_amount or 0),
        "posted_payment_amount": posted_payments,
        "ap_mirror_id": payable.id if payable else None,
        "ap_outstanding_amount": Decimal(payable.outstanding_amount or 0) if payable else None,
        "accounting_exception": bool(exceptions),
        "accounting_exception_codes": exceptions,
    }
