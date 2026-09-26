#!/usr/bin/env python3
"""Repair historical PT. SUKANDA DJAYA supplier invoices whose header/AP total omitted PPN.

Creates an auditable posted correction journal (Dr Input VAT / Cr Accounts Payable)
instead of mutating the already-posted original invoice journal.

Targets are source-proven RESIPING invoices:
- HIST-INVOICE-70:  5,417,238 + 595,896 PPN = 6,013,134
- HIST-INVOICE-93:  6,634,893 + 681,388 PPN = 7,316,281

Dry-run by default. Use --apply after reviewing output.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "resiping-historical-repair-local-0123456789abcdef")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func

from app.core.database import SessionLocal
from app.models.account_payable import AccountPayable
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.payment import Payment, PaymentAllocation
from app.models.supplier_invoice import SupplierInvoice
from app.models.user import User
from app.services.direct_coa_service import DirectCoaService
from app.services.document_number import next_document_number
from app.services.general_ledger import GeneralLedgerService

ZERO = Decimal("0")

TARGETS = {
    "HIST-INVOICE-70": {
        "pre_tax_total": Decimal("5417238.00"),
        "tax": Decimal("595896.00"),
        "gross_total": Decimal("6013134.00"),
    },
    "HIST-INVOICE-93": {
        "pre_tax_total": Decimal("6634893.00"),
        "tax": Decimal("681388.00"),
        "gross_total": Decimal("7316281.00"),
    },
}


def posted_payment_total(db, invoice_id: int) -> Decimal:
    value = (
        db.query(func.coalesce(func.sum(PaymentAllocation.allocated_amount), 0))
        .join(Payment, Payment.id == PaymentAllocation.payment_id)
        .filter(
            PaymentAllocation.supplier_invoice_id == invoice_id,
            Payment.status == "POSTED",
        )
        .scalar()
    )
    return Decimal(value or 0)


def payable_mirror(db, invoice: SupplierInvoice):
    return (
        db.query(AccountPayable)
        .filter(
            AccountPayable.supplier_id == invoice.supplier_id,
            AccountPayable.invoice_number == invoice.internal_invoice_number,
        )
        .first()
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default="admin")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == args.user).first()
        if not user:
            raise RuntimeError(f"user {args.user!r} not found")

        print("MODE:", "APPLY" if args.apply else "DRY RUN")
        planned = []

        for supplier_invoice_number, expected in TARGETS.items():
            invoice = (
                db.query(SupplierInvoice)
                .filter(SupplierInvoice.supplier_invoice_number == supplier_invoice_number)
                .with_for_update()
                .one_or_none()
            )
            if not invoice:
                raise RuntimeError(f"{supplier_invoice_number}: supplier invoice not found")
            if invoice.source_type != "HISTORICAL_IMPORT":
                raise RuntimeError(f"{supplier_invoice_number}: refusing non-historical invoice")
            if invoice.status != "POSTED":
                raise RuntimeError(f"{supplier_invoice_number}: expected POSTED, found {invoice.status}")

            total = Decimal(invoice.total_amount or 0)
            tax = Decimal(invoice.tax_amount or 0)
            paid = posted_payment_total(db, invoice.id)

            if tax not in {ZERO, expected["tax"]}:
                raise RuntimeError(
                    f"{supplier_invoice_number}: expected stored tax 0 or {expected['tax']}, found {tax}"
                )
            if paid != ZERO:
                raise RuntimeError(
                    f"{supplier_invoice_number}: already has posted payments {paid}; manual reconciliation required"
                )

            correction = (
                db.query(JournalEntry)
                .filter(
                    JournalEntry.reference_type == "HISTORICAL_PPN_REPAIR",
                    JournalEntry.reference_id == invoice.id,
                    JournalEntry.status != "VOID",
                )
                .first()
            )

            if total not in {expected["pre_tax_total"], expected["gross_total"]}:
                raise RuntimeError(
                    f"{supplier_invoice_number}: expected current total {expected['pre_tax_total']} "
                    f"or repaired total {expected['gross_total']}, found {total}"
                )

            resolver = DirectCoaService(db)
            vat = resolver.input_vat_account()
            ap = resolver.payable_account(invoice.supplier, invoice.location_id)

            original = (
                db.query(JournalEntry)
                .filter(
                    JournalEntry.reference_type == "SUPPLIER_INVOICE",
                    JournalEntry.reference_id == invoice.id,
                    JournalEntry.status == "POSTED",
                )
                .order_by(JournalEntry.id.desc())
                .first()
            )
            if not original:
                raise RuntimeError(f"{supplier_invoice_number}: posted supplier-invoice journal missing")

            vat_debit = sum(
                (Decimal(line.debit or 0) for line in original.lines if line.account_id == vat.id),
                ZERO,
            )
            ap_credit = sum(
                (Decimal(line.credit or 0) for line in original.lines if line.account_id == ap.id),
                ZERO,
            )

            journal_already_gross = (
                vat_debit == expected["tax"]
                and ap_credit == expected["gross_total"]
            )
            journal_missing_ppn = (
                vat_debit == ZERO
                and ap_credit == expected["pre_tax_total"]
            )

            if not journal_already_gross and not journal_missing_ppn:
                raise RuntimeError(
                    f"{supplier_invoice_number}: unexpected original journal state "
                    f"(VAT debit={vat_debit}, AP credit={ap_credit}); refusing automatic repair"
                )

            needs_correction = journal_missing_ppn
            if journal_already_gross:
                print(
                    f"{supplier_invoice_number}: original journal already includes PPN "
                    f"(VAT={vat_debit}, AP={ap_credit}); no correction journal needed"
                )
            elif correction:
                print(
                    f"{supplier_invoice_number}: PPN correction already exists "
                    f"({correction.journal_number})"
                )

            if needs_correction and correction is None:
                correction = JournalEntry(
                    journal_number=next_document_number(db, "JV", digits=4),
                    posting_date=invoice.invoice_date,
                    status="POSTED",
                    document_type="HISTORICAL_PPN_REPAIR",
                    document_number=invoice.internal_invoice_number,
                    reference_type="HISTORICAL_PPN_REPAIR",
                    reference_id=invoice.id,
                    description=f"Historical PPN correction for {invoice.supplier_invoice_number}",
                    created_by_id=user.id,
                    posted_by_id=user.id,
                    posted_at=datetime.now(timezone.utc),
                    business_unit_id=invoice.business_unit_id,
                    location_id=invoice.location_id,
                    department_id=invoice.department_id,
                )
                correction.lines.append(JournalLine(
                    line_number=1,
                    account_id=vat.id,
                    debit=expected["tax"],
                    credit=ZERO,
                    description=f"Input VAT historical correction {invoice.supplier_invoice_number}",
                    supplier_id=invoice.supplier_id,
                    business_unit_id=invoice.business_unit_id,
                    location_id=invoice.location_id,
                    department_id=invoice.department_id,
                ))
                correction.lines.append(JournalLine(
                    line_number=2,
                    account_id=ap.id,
                    debit=ZERO,
                    credit=expected["tax"],
                    description=f"AP historical PPN correction {invoice.supplier_invoice_number}",
                    supplier_id=invoice.supplier_id,
                    business_unit_id=invoice.business_unit_id,
                    location_id=invoice.location_id,
                    department_id=invoice.department_id,
                ))
                db.add(correction)
                db.flush()

                if args.apply:
                    GeneralLedgerService.post(
                        db=db,
                        account_id=vat.id,
                        debit=expected["tax"],
                        credit=ZERO,
                        posting_date=invoice.invoice_date,
                        journal_source="HISTORICAL_PPN_REPAIR",
                        document_type=correction.document_type,
                        document_number=correction.document_number,
                        reference_type=correction.reference_type,
                        reference_id=invoice.id,
                        reference_number=correction.journal_number,
                        description=correction.lines[0].description,
                        user_id=user.id,
                    )
                    GeneralLedgerService.post(
                        db=db,
                        account_id=ap.id,
                        debit=ZERO,
                        credit=expected["tax"],
                        posting_date=invoice.invoice_date,
                        journal_source="HISTORICAL_PPN_REPAIR",
                        document_type=correction.document_type,
                        document_number=correction.document_number,
                        reference_type=correction.reference_type,
                        reference_id=invoice.id,
                        reference_number=correction.journal_number,
                        description=correction.lines[1].description,
                        user_id=user.id,
                    )

            invoice.tax_amount = expected["tax"]
            invoice.total_amount = expected["gross_total"]
            invoice.balance_amount = expected["gross_total"]
            invoice.paid_amount = ZERO
            invoice.payment_status = "UNPAID"

            payable = payable_mirror(db, invoice)
            if not payable:
                raise RuntimeError(f"{supplier_invoice_number}: AP mirror missing")
            payable.amount = expected["gross_total"]
            payable.paid_amount = ZERO
            payable.outstanding_amount = expected["gross_total"]
            payable.payment_status = "UNPAID"
            payable.status = "OPEN"

            planned.append((
                supplier_invoice_number,
                invoice.internal_invoice_number,
                expected["pre_tax_total"],
                expected["tax"],
                expected["gross_total"],
                correction.journal_number if correction else "NOT_REQUIRED",
            ))

        print("\n=== REPAIR CONTROL ===")
        for supplier_ref, internal_no, pre_tax, tax, gross, journal_no in planned:
            print(
                f"{supplier_ref} | {internal_no} | {pre_tax} + PPN {tax} = {gross} "
                f"| correction={journal_no}"
            )

        if args.apply:
            db.commit()
            print("\nRESULT: APPLIED")
        else:
            db.rollback()
            print("\nRESULT: DRY RUN ONLY")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
