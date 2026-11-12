"""Consolidate verified bank-transfer pairs from the January Catering draft seed."""
import argparse
from datetime import date, datetime, timezone
from pathlib import Path

from seed_catering_january_journals import journal_reference, load_source, prepare

PAIRS = (
    (35, 39), (37, 38), (224, 252), (405, 407), (473, 796), (844, 941),
    (847, 849), (1018, 996), (1105, 1081), (1112, 1127), (1150, 1136),
    (1158, 1470), (1159, 1544), (1162, 1472), (1563, 1593), (1566, 1582),
    (1828, 2120),
)


def source_pairs(path):
    drafts, _ = prepare(load_source(path))
    rows = {row[0]: row for row in drafts}
    for outgoing, incoming in PAIRS:
        debit_side, credit_side = rows[incoming], rows[outgoing]
        if (credit_side[1] != debit_side[1] or credit_side[3] == debit_side[3]
                or credit_side[4] or debit_side[5] or not credit_side[5]
                or credit_side[5] != debit_side[4] or credit_side[6] or debit_side[6]):
            raise ValueError(f"Source transfer pair changed: {outgoing}/{incoming}")
        yield credit_side, debit_side


def repair(path, apply):
    from sqlalchemy import text

    from app import models  # noqa: F401
    from app.api.v1.journals import validate
    from app.core.database import SessionLocal
    from app.models.business_unit import BusinessUnit
    from app.models.journal_entry import JournalEntry
    from app.models.journal_line import JournalLine
    from app.services.activity_service import ActivityService
    from app.services.fiscal_period_service import FiscalPeriodService

    pairs = list(source_pairs(path))
    refs = {journal_reference(row[0]) for pair in pairs for row in pair}
    with SessionLocal() as db, db.begin():
        if apply:
            db.execute(text("SET LOCAL lock_timeout = '15s'"))
            FiscalPeriodService.validate_posting_date(db, date(2026, 1, 1))
            db.execute(text("LOCK TABLE journal_entries, journal_lines IN SHARE ROW EXCLUSIVE MODE"))
        else:
            db.execute(text("SET TRANSACTION READ ONLY"))

        unit = db.query(BusinessUnit).filter_by(name="Project Catering").one()
        found = db.query(JournalEntry).filter(JournalEntry.external_reference.in_(refs)).all()
        entries = {entry.external_reference: entry for entry in found}
        if len(found) != len(refs) or set(entries) != refs:
            raise ValueError("Expected exactly one seeded draft record per transfer reference")

        pending = []
        for outgoing, incoming in pairs:
            sender, receiver = (entries[journal_reference(row[0])] for row in (outgoing, incoming))
            for entry, row in ((sender, outgoing), (receiver, incoming)):
                if (entry.business_unit_id != unit.id or entry.posting_date != row[1]
                        or entry.document_number != journal_reference(row[0])
                        or entry.source_type != "JOURNAL_IMPORT" or entry.reference_type != "MANUAL"
                        or entry.reference_id != 0 or entry.posted_at is not None
                        or entry.description != row[2]):
                    raise ValueError(f"Seeded journal changed: {entry.external_reference}")
            if sender.location_id is None or sender.location_id != receiver.location_id:
                raise ValueError(f"Transfer location mismatch: {sender.external_reference}")

            def line_values(entry):
                return sorted((line.account.account_number, line.debit, line.credit,
                               line.location_id, line.business_unit_id) for line in entry.lines)

            sender_line, receiver_line = [
                (row[3], row[4], row[5], entry.location_id, unit.id)
                for entry, row in ((sender, outgoing), (receiver, incoming))
            ]
            if (sender.status == "DRAFT" and receiver.status == "VOID"
                    and line_values(sender) == sorted([sender_line, receiver_line])
                    and line_values(receiver) == [receiver_line]):
                continue
            if (sender.status != "DRAFT" or receiver.status != "DRAFT"
                    or line_values(sender) != [sender_line] or line_values(receiver) != [receiver_line]):
                raise ValueError(f"Draft lines or status changed: {sender.external_reference}, {receiver.external_reference}")
            pending.append((sender, receiver))

        print(f"Verified {len(pairs)} pairs, {len(pending)} pending, {len(pairs) - len(pending)} already consolidated.")
        if not apply:
            for sender, receiver in pending:
                print(f"{sender.external_reference} + {receiver.external_reference}")
            return

        for sender, receiver in pending:
            FiscalPeriodService.validate_posting_date(db, sender.posting_date)
            line = receiver.lines[0]
            sender.lines.append(JournalLine(
                line_number=2, account_id=line.account_id, debit=line.debit, credit=line.credit,
                description=line.description, location_id=line.location_id,
                business_unit_id=line.business_unit_id, department_id=line.department_id,
            ))
            debit, credit = validate(db, sender.lines)
            if debit != credit:
                raise ValueError(f"Combined transfer does not balance: {sender.external_reference}")
            receiver.status = "VOID"
            receiver.voided_at = datetime.now(timezone.utc)
            for entry, action, other in ((sender, "JOURNAL_UPDATED", receiver),
                                         (receiver, "JOURNAL_VOIDED", sender)):
                ActivityService.log(
                    db=db, user=None, action=action, entity_type="JOURNAL_ENTRY", entity_id=entry.id,
                    summary=f"Consolidated Kas Harian transfer {sender.external_reference} / {receiver.external_reference}",
                    document_number=entry.document_number, document_status=entry.status,
                    details={"actor": "SYSTEM", "paired_journal_id": other.id,
                             "paired_reference": other.external_reference},
                )
    print(f"COMMITTED {len(pending)} transfer replacements.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xlsx", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    repair(args.xlsx, args.apply)
