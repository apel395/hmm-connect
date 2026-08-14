from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.account_payable import AccountPayable
from app.models.supplier_invoice import SupplierInvoice

ZERO = Decimal("0")


def invoice_balance(invoice: SupplierInvoice) -> Decimal:
    return max(
        ZERO,
        Decimal(invoice.total_amount or 0)
        - Decimal(invoice.paid_amount or 0)
        - Decimal(invoice.adjustment_amount or 0),
    )


def sync_invoice_balance(invoice: SupplierInvoice) -> Decimal:
    balance = invoice_balance(invoice)
    invoice.balance_amount = balance
    invoice.payment_status = (
        "PAID"
        if balance == ZERO and Decimal(invoice.total_amount or 0) > ZERO
        else "PARTIALLY_PAID"
        if Decimal(invoice.paid_amount or 0) > ZERO or Decimal(invoice.adjustment_amount or 0) > ZERO
        else "UNPAID"
    )
    return balance


def payable_for_invoice(db: Session, invoice: SupplierInvoice) -> AccountPayable | None:
    return (
        db.query(AccountPayable)
        .filter(
            AccountPayable.supplier_id == invoice.supplier_id,
            AccountPayable.invoice_number == invoice.internal_invoice_number,
        )
        .first()
    )


def sync_account_payable(
    db: Session,
    invoice: SupplierInvoice,
    *,
    matched: bool | None = None,
    match_status: str | None = None,
    match_note: str | None = None,
    payment_date: date | None = None,
    create_if_missing: bool = True,
) -> AccountPayable | None:
    balance = sync_invoice_balance(invoice)
    payable = payable_for_invoice(db, invoice)

    if payable is None and create_if_missing:
        payable = AccountPayable(
            supplier_id=invoice.supplier_id,
            purchase_order_id=invoice.purchase_order_id,
            invoice_number=invoice.internal_invoice_number,
            invoice_date=invoice.invoice_date,
            due_date=invoice.due_date,
            amount=invoice.total_amount,
            paid_amount=invoice.paid_amount or ZERO,
            outstanding_amount=balance,
            status="PAID" if balance == ZERO else "OPEN",
            payment_status=invoice.payment_status,
            matched=bool(matched),
            match_status=match_status or "PENDING",
            match_note=match_note,
        )
        db.add(payable)
        return payable

    if payable is None:
        return None

    payable.purchase_order_id = invoice.purchase_order_id
    payable.invoice_date = invoice.invoice_date
    payable.due_date = invoice.due_date
    payable.amount = invoice.total_amount
    payable.paid_amount = invoice.paid_amount or ZERO
    payable.outstanding_amount = balance
    payable.payment_status = invoice.payment_status
    payable.status = "PAID" if balance == ZERO else "OPEN"
    if matched is not None:
        payable.matched = matched
    if match_status is not None:
        payable.match_status = match_status
    if match_note is not None:
        payable.match_note = match_note
    if payment_date is not None:
        payable.last_payment_date = payment_date
    return payable
