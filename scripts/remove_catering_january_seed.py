"""Delete the January 2026 Project Catering Kas Harian seed drafts."""
import argparse
from datetime import date

from seed_catering_january_journals import PREFIX, journal_reference

EXPECTED_COUNT = 2263
FIRST_DAY = date(2026, 1, 1)
LAST_DAY = date(2026, 1, 31)
NON_JOURNAL_ROWS = {255, 376, 480, 850, 1163, 1473, 1698, 1831}
EXPECTED_REFS = {journal_reference(row) for row in range(24, 2293) if row not in NON_JOURNAL_ROWS}
EXPECTED_REFS.update({journal_reference("0376-PHM"), journal_reference("0376-DOBS")})


def remove(apply):
    from sqlalchemy import text

    from app import models  # noqa: F401
    from app.core.database import SessionLocal
    from app.models.audit_log import AuditLog
    from app.models.business_unit import BusinessUnit
    from app.models.journal_entry import JournalEntry
    from app.services.activity_service import ActivityService

    with SessionLocal() as db, db.begin():
        if apply:
            db.execute(text("SET LOCAL lock_timeout = '15s'"))
            db.execute(text("LOCK TABLE journal_entries, journal_lines IN SHARE ROW EXCLUSIVE MODE"))
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
            if (journal.document_number != ref
                    or journal.business_unit_id != unit.id or not FIRST_DAY <= journal.posting_date <= LAST_DAY
                    or journal.status not in {"DRAFT", "VOID"} or journal.posted_at is not None
                    or journal.posted_by_id is not None or journal.reference_type != "MANUAL"
                    or journal.reference_id != 0 or journal.source_type != "JOURNAL_IMPORT"
                    or journal.document_type != "BULK_JOURNAL_IMPORT"):
                raise ValueError(f"Journal is outside the unposted seed scope: {ref}")

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

        line_count = sum(len(journal.lines) for journal in journals)
        print(f"Verified {len(journals)} January Catering seed journals and {line_count} journal lines.")
        if not apply:
            return

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
    print(f"COMMITTED removal of {len(journals)} January Catering seed journals and {line_count} lines.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    remove(parser.parse_args().apply)
