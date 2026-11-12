"""Delete the January 2026 Project Catering Kas Harian seed journals and their GL rows."""
import argparse
from datetime import date

from seed_catering_january_journals import PREFIX, journal_reference

EXPECTED_COUNT = 2246
FIRST_DAY = date(2026, 1, 1)
LAST_DAY = date(2026, 1, 31)
NON_JOURNAL_ROWS = {255, 376, 480, 850, 1163, 1473, 1698, 1831}
# Outgoing rows folded into their receiving journals by seed commit 13da5ce.
CONSOLIDATED_OUTGOING_ROWS = {
    35, 37, 224, 405, 473, 844, 847, 1018, 1105, 1112, 1150, 1158,
    1159, 1162, 1563, 1566, 1828,
}
EXPECTED_REFS = {
    journal_reference(row) for row in range(24, 2293)
    if row not in NON_JOURNAL_ROWS | CONSOLIDATED_OUTGOING_ROWS
}
EXPECTED_REFS.update({journal_reference("0376-PHM"), journal_reference("0376-DOBS")})


def remove(apply):
    from sqlalchemy import text

    from app import models  # noqa: F401
    from app.core.database import SessionLocal
    from app.models.audit_log import AuditLog
    from app.models.business_unit import BusinessUnit
    from app.models.general_ledger import GeneralLedger
    from app.models.journal_entry import JournalEntry
    from app.services.activity_service import ActivityService
    from app.services.fiscal_period_service import FiscalPeriodService

    with SessionLocal() as db, db.begin():
        if apply:
            db.execute(text("SET LOCAL lock_timeout = '15s'"))
            FiscalPeriodService.validate_posting_date(db, FIRST_DAY)
            db.execute(text("LOCK TABLE journal_entries, journal_lines, general_ledger IN SHARE ROW EXCLUSIVE MODE"))
        else:
            db.execute(text("SET TRANSACTION READ ONLY"))

        unit = db.query(BusinessUnit).filter_by(name="Project Catering").one()
        journals = db.query(JournalEntry).filter(JournalEntry.external_reference.like(PREFIX + "%")).all()
        if not journals:
            print("No January Catering seed journals found.")
            return

        refs = {journal.external_reference for journal in journals}
        if len(journals) != EXPECTED_COUNT or refs != EXPECTED_REFS:
            raise ValueError(f"Expected {EXPECTED_COUNT} unique seed references, found {len(journals)} journals.")
        for journal in journals:
            ref = journal.external_reference
            if (journal.business_unit_id != unit.id or not FIRST_DAY <= journal.posting_date <= LAST_DAY
                    or journal.status not in {"DRAFT", "VOID", "POSTED"}
                    or journal.reference_type != "MANUAL" or journal.reference_id != 0):
                raise ValueError(f"Journal is outside the manual January Catering seed scope: {ref} "
                                 f"(status={journal.status}, date={journal.posting_date}, "
                                 f"unit={journal.business_unit_id}, reference={journal.reference_type}/{journal.reference_id})")

        provenance = {
            (entity_id, document_number)
            for entity_id, document_number in db.query(AuditLog.entity_id, AuditLog.document_number).filter(
                AuditLog.entity_type == "JOURNAL_ENTRY",
                AuditLog.action == "JOURNAL_IMPORT_CREATED",
                AuditLog.document_number.in_(refs),
            )
        }
        if any((journal.id, journal.external_reference) not in provenance for journal in journals):
            raise ValueError("At least one journal has no matching seed creation audit record.")

        journals_by_number = {journal.journal_number: journal for journal in journals}
        ledger_rows = db.query(GeneralLedger).filter(
            GeneralLedger.reference_number.in_(journals_by_number),
        ).all()
        for ledger_row in ledger_rows:
            journal = journals_by_number[ledger_row.reference_number]
            if ledger_row.reference_type != journal.reference_type or ledger_row.reference_id != journal.reference_id:
                raise ValueError(f"Unexpected GL reference for {journal.journal_number}")

        line_count = sum(len(journal.lines) for journal in journals)
        posted_count = sum(journal.status == "POSTED" for journal in journals)
        print(f"Verified {len(journals)} January Catering seed journals ({posted_count} posted), "
              f"{line_count} journal lines, and {len(ledger_rows)} GL rows.")
        if not apply:
            return

        for posting_date in sorted({journal.posting_date for journal in journals}):
            FiscalPeriodService.validate_posting_date(db, posting_date)
        for ledger_row in ledger_rows:
            db.delete(ledger_row)

        for journal in journals:
            ActivityService.log(
                db=db, user=None, action="JOURNAL_SEED_REMOVED", entity_type="JOURNAL_ENTRY",
                entity_id=journal.id, summary=f"Removed January Catering seed {journal.external_reference}",
                document_number=journal.document_number, document_status=journal.status,
                details={"actor": "SYSTEM", "journal_number": journal.journal_number},
            )
            db.delete(journal)
        db.flush()
        if db.query(JournalEntry).filter(JournalEntry.external_reference.like(PREFIX + "%")).count():
            raise RuntimeError("Seed journals remain after deletion")
    print(f"COMMITTED removal of {len(journals)} January Catering seed journals, "
          f"{line_count} journal lines and {len(ledger_rows)} GL rows.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    remove(parser.parse_args().apply)
