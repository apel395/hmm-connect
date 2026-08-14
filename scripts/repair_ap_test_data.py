"""Repair legacy AP test data created before invoice-posting payment guards.

Usage:
    python scripts/repair_ap_test_data.py             # dry-run
    python scripts/repair_ap_test_data.py --apply     # apply repairs

The command only repairs an invoice when all of the following are true:
- at least one POSTED supplier payment allocates to the invoice;
- no POSTED SUPPLIER_INVOICE journal exists;
- exactly one DRAFT SUPPLIER_INVOICE journal exists;
- no General Ledger rows already exist for that draft journal;
- the draft journal is balanced and contains valid debit/credit lines.

It never deletes invoices, payments, journals, or GL rows. Ambiguous cases are
reported and skipped.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal

from app.core.database import SessionLocal
from app.models.general_ledger import GeneralLedger
from app.models.journal_entry import JournalEntry
from app.models.payment import Payment, PaymentAllocation
from app.models.supplier_invoice import SupplierInvoice
from app.services.general_ledger import GeneralLedgerService

ZERO = Decimal("0")


def posted_payment_total(db, invoice_id: int) -> Decimal:
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


def invoice_journals(db, invoice_id: int):
    return (
        db.query(JournalEntry)
        .filter(
            JournalEntry.reference_type == "SUPPLIER_INVOICE",
            JournalEntry.reference_id == invoice_id,
        )
        .order_by(JournalEntry.id.asc())
        .all()
    )


def existing_gl_rows(db, invoice_id: int, journal_number: str):
    return (
        db.query(GeneralLedger)
        .filter(
            GeneralLedger.reference_type == "SUPPLIER_INVOICE",
            GeneralLedger.reference_id == invoice_id,
            GeneralLedger.reference_number == journal_number,
        )
        .all()
    )


def journal_totals(journal: JournalEntry) -> tuple[Decimal, Decimal, bool]:
    debit = ZERO
    credit = ZERO
    valid = bool(journal.lines)
    for line in journal.lines:
        line_debit = Decimal(line.debit or 0)
        line_credit = Decimal(line.credit or 0)
        if line_debit < ZERO or line_credit < ZERO or (line_debit > ZERO) == (line_credit > ZERO):
            valid = False
        debit += line_debit
        credit += line_credit
    return debit, credit, valid


def inspect_invoice(db, invoice: SupplierInvoice) -> dict:
    payment_total = posted_payment_total(db, invoice.id)
    journals = invoice_journals(db, invoice.id)
    posted = [journal for journal in journals if journal.status == "POSTED"]
    drafts = [journal for journal in journals if journal.status == "DRAFT"]

    result = {
        "invoice": invoice,
        "posted_payment_total": payment_total,
        "posted_journals": posted,
        "draft_journals": drafts,
        "repairable": False,
        "reason": None,
        "journal": None,
    }

    if payment_total <= ZERO:
        result["reason"] = "no posted supplier payment"
        return result
    if posted:
        result["reason"] = "invoice journal already posted"
        return result
    if len(drafts) != 1:
        result["reason"] = f"expected exactly one draft invoice journal, found {len(drafts)}"
        return result

    journal = drafts[0]
    gl_rows = existing_gl_rows(db, invoice.id, journal.journal_number)
    if gl_rows:
        result["reason"] = f"draft journal already has {len(gl_rows)} GL row(s); manual inspection required"
        return result

    debit, credit, lines_valid = journal_totals(journal)
    if not lines_valid:
        result["reason"] = "draft journal contains invalid debit/credit lines"
        return result
    if debit != credit or debit <= ZERO:
        result["reason"] = f"draft journal is not balanced (debit={debit}, credit={credit})"
        return result

    result["repairable"] = True
    result["journal"] = journal
    result["reason"] = "safe to post existing invoice journal"
    return result


def repair_one(db, state: dict):
    invoice: SupplierInvoice = state["invoice"]
    journal: JournalEntry = state["journal"]

    # Lock the accounting records and re-check the critical invariants.
    invoice = db.query(SupplierInvoice).filter(SupplierInvoice.id == invoice.id).with_for_update().one()
    journal = db.query(JournalEntry).filter(JournalEntry.id == journal.id).with_for_update().one()

    if journal.status != "DRAFT":
        raise RuntimeError(f"{journal.journal_number} is no longer DRAFT")
    if existing_gl_rows(db, invoice.id, journal.journal_number):
        raise RuntimeError(f"{journal.journal_number} already has GL rows")

    debit, credit, lines_valid = journal_totals(journal)
    if not lines_valid or debit != credit or debit <= ZERO:
        raise RuntimeError(f"{journal.journal_number} is no longer a valid balanced journal")

    actor_id = journal.created_by_id or invoice.created_by_id
    if not actor_id:
        raise RuntimeError(f"{journal.journal_number} has no user identity for GL audit fields")

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
            user_id=actor_id,
        )

    now = datetime.now(timezone.utc)
    journal.status = "POSTED"
    journal.posted_by_id = actor_id
    journal.posted_at = now
    invoice.status = "POSTED"
    invoice.posted_at = now


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair legacy AP test-data accounting inconsistencies")
    parser.add_argument("--apply", action="store_true", help="Apply safe repairs. Without this flag the command is dry-run only.")
    args = parser.parse_args()

    db = SessionLocal()
    repaired = 0
    skipped = 0
    candidates = 0
    try:
        invoices = db.query(SupplierInvoice).order_by(SupplierInvoice.id.asc()).all()
        print(f"Scanning {len(invoices)} supplier invoice(s)...")

        for invoice in invoices:
            state = inspect_invoice(db, invoice)
            if state["posted_payment_total"] <= ZERO:
                continue
            candidates += 1
            label = f"{invoice.internal_invoice_number} (id={invoice.id})"
            payment_total = state["posted_payment_total"]

            if not state["repairable"]:
                skipped += 1
                print(f"SKIP   {label}: posted payments={payment_total}; {state['reason']}")
                continue

            journal = state["journal"]
            if not args.apply:
                print(f"REPAIR {label}: would post {journal.journal_number}; posted payments={payment_total}")
                continue

            try:
                repair_one(db, state)
                db.commit()
                repaired += 1
                print(f"FIXED  {label}: posted {journal.journal_number}")
            except Exception as exc:
                db.rollback()
                skipped += 1
                print(f"ERROR  {label}: {exc}")

        mode = "APPLY" if args.apply else "DRY-RUN"
        print(f"{mode} complete: candidates={candidates}, repaired={repaired}, skipped={skipped}")
        if not args.apply:
            print("Run again with --apply after reviewing the dry-run output.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
