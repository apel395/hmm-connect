"""Seed/post January Hotel manual journals, preserving source imbalance and audit."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from prepare_hotel_january_journals import build_plan, inspect_database, read_source

# User explicitly authorized keeping the source difference and correcting in app.
ALLOWED_SOURCE_WARNINGS = {"UNBALANCED_SOURCE_REGISTER"}


def select_groups(plan):
    create, present, skipped = [], [], []
    for journal in plan["source"]["journals"]:
        if journal.get("existing_journals"):
            present.append(journal)
        elif set(journal["issues"]) - ALLOWED_SOURCE_WARNINGS:
            skipped.append(journal)
        else:
            create.append(journal)
    return create, present, skipped


def resolve_actor(db, user_id=None, *, interactive=False):
    from app.dependencies.authorization import is_superuser
    from app.models.user import User

    admins = [u for u in db.query(User).filter(User.is_active.is_(True)).all() if is_superuser(u)]
    if user_id is None and len(admins) == 1:
        user_id = admins[0].id
    if user_id is None and interactive and sys.stdin.isatty():
        print("Select the administrator recorded as import/posting actor:")
        for actor in admins:
            print(f"  {actor.id}: {actor.username} — {actor.full_name}")
        user_id = int(input("Administrator user ID: "))
    actor = next((u for u in admins if u.id == user_id), None)
    if actor is None:
        choices = [{"id": u.id, "username": u.username} for u in admins]
        raise ValueError(f"An active SYSTEM_ADMINISTRATOR actor is required. Use --user-id. Candidates: {choices}")
    return actor


def assert_existing_provenance(db, journal, source_hash):
    from app.models.import_batch import ImportBatch
    from app.models.journal_entry import JournalEntry

    matches = db.query(JournalEntry).filter_by(external_reference=journal["external_reference"]).all()
    if len(matches) != 1:
        raise ValueError(f"Register {journal['register']} has a legacy/ambiguous existing identity; do not duplicate it")
    existing = matches[0]
    batch = db.get(ImportBatch, existing.import_batch_id) if existing.import_batch_id else None
    provenance = json.loads(batch.notes or "{}") if batch else {}
    if provenance.get("source_sha256") != source_hash:
        raise ValueError(f"Register {journal['register']} already exists without this seed's provenance; inspection required")
    # Intentionally never overwrite app corrections, voids or unposts on rerun.
    return {"register": journal["register"], "id": existing.id, "status": existing.status}


def seed(db, source, mapping, actor, *, apply=False, post=False):
    from sqlalchemy import text
    from app.api.v1.journals import post_locked_journal, validate
    from app.models.import_batch import ImportBatch, ImportRow
    from app.models.journal_entry import JournalEntry
    from app.models.journal_line import JournalLine
    from app.services.activity_service import ActivityService
    from app.services.document_number import next_document_number
    from app.services.fiscal_period_service import FiscalPeriodService
    from app.services.organization_dimensions import validate_dimensions

    if db.bind.dialect.name == "postgresql":
        # Serialize this seed and keep concurrent journal create/edit/unpost from
        # changing duplicate evidence during the single atomic transaction.
        db.execute(text("SET LOCAL lock_timeout = '15s'"))
        db.execute(text("LOCK TABLE journal_entries, journal_lines IN SHARE ROW EXCLUSIVE MODE"))
    snapshot = inspect_database(db.connection())
    plan = build_plan(source, snapshot, mapping)
    create, present, skipped = select_groups(plan)
    existing = [assert_existing_provenance(db, j, source["source_sha256"]) for j in present]
    result = {
        "mode": "APPLY" if apply else "DRY_RUN", "target_status": "POSTED" if post else "DRAFT",
        "source_sha256": source["source_sha256"], "new_journals": len(create),
        "financial_lines": sum(sum(not l.get("omit_zero_value") for l in j["lines"]) for j in create),
        "already_present": existing,
        "skipped": [{"register": j["register"], "issues": j["issues"], "possible_existing_journals": j.get("possible_existing_journals", [])} for j in skipped],
        "skip_counts": dict(Counter(i for j in skipped for i in j["issues"])),
        "debit": str(sum((Decimal(j["debit"]) for j in create), Decimal(0))),
        "credit": str(sum((Decimal(j["credit"]) for j in create), Decimal(0))),
        "source_differences_preserved": [{"register": j["register"], "difference": j["difference"]} for j in create if Decimal(j["difference"])],
        "created": [],
    }
    if not apply or not create:
        return result
    if actor is None:
        raise ValueError("Import actor required")
    scope = mapping["scope"]
    validate_dimensions(db, **scope, required=True)
    # Hold/revalidate the open period before any journal is added.
    for value in sorted({j["posting_date"] for j in create}):
        FiscalPeriodService.validate_posting_date(db=db, posting_date=date.fromisoformat(value))
    now = datetime.now(timezone.utc)
    batch = ImportBatch(
        batch_number=f"HJ26-{uuid.uuid4().hex[:20]}", batch_name="Hotel January 2026 journal seed",
        source="LEGACY_SYSTEM", import_type="JOURNAL", import_mode="STRICT", source_type="JOURNAL_IMPORT",
        description="User authorized source-preserving historical manual journals; corrections through app unpost/edit.",
        imported_by_id=actor.id, created_by_id=actor.id, period_from=date(2026, 1, 1), period_to=date(2026, 1, 31),
        file_name=source["source_file"], original_file_name=source["source_file"],
        total_documents=len(create), total_rows=sum(len(j["lines"]) for j in create),
        status="PROCESSING", notes=json.dumps({"source_sha256": source["source_sha256"],
            "mapping_sha256": hashlib.sha256(json.dumps(mapping, sort_keys=True).encode()).hexdigest(),
            "source_imbalance_preserved": True, "post_requested": post}),
    )
    db.add(batch)
    db.flush()
    for group in create:
        active = [line for line in group["lines"] if not line.get("omit_zero_value")]
        departments = {line.get("department_id") for line in active}
        journal = JournalEntry(
            journal_number=next_document_number(db, "MAN", digits=6),
            posting_date=date.fromisoformat(group["posting_date"]), fiscal_year=2026, fiscal_period=1,
            status="DRAFT", posted_at=None, document_type="BULK_JOURNAL_IMPORT",
            document_number=(group.get("invoice_reference") or f"REG-{group['register']}")[:100],
            reference_type="MANUAL", reference_id=0, description=group["description"],
            created_by_id=actor.id, source_type="JOURNAL_IMPORT", external_reference=group["external_reference"],
            import_batch_id=batch.id, imported_by_id=actor.id, imported_at=now,
            business_unit_id=scope["business_unit_id"], location_id=scope["location_id"],
            department_id=next(iter(departments)) if len(departments) == 1 else None,
        )
        for number, line in enumerate(active, 1):
            validate_dimensions(db, **scope, department_id=line.get("department_id"), required=True)
            journal.lines.append(JournalLine(
                line_number=number, account_id=line["account_id"], debit=Decimal(line["debit"]), credit=Decimal(line["credit"]),
                description=line.get("description"), business_unit_id=scope["business_unit_id"],
                location_id=scope["location_id"], department_id=line.get("department_id"),
            ))
        validate(db, journal.lines)
        db.add(journal)
        db.flush()
        for line in group["lines"]:
            db.add(ImportRow(
                import_batch_id=batch.id, row_number=line["source_row"], sheet_name=source["sheet"], document_type="JOURNAL",
                raw_data_json={"source_sha256": source["source_sha256"], "register": group["register"],
                    "header_row": group["header_row"], "source_row": line["source_row"], "legacy_code": line["legacy_code"],
                    "legacy_name": line["legacy_name"], "source_account_code": line["source_account_code"],
                    "source_dc": line["source_dc"], "debit": line["debit"], "credit": line["credit"],
                    "description": line.get("description"), "invoice_reference": group.get("invoice_reference")},
                normalized_data_json=dict(line), status="IMPORTED", entity_type="JOURNAL_ENTRY", entity_id=journal.id,
                document_number=journal.document_number, imported_at=now,
                warning_messages_json=["SOURCE_IMBALANCE_PRESERVED"] if Decimal(group["difference"]) else [],
            ))
        ActivityService.log(db=db, user=actor, action="JOURNAL_IMPORT_CREATED", entity_type="JOURNAL_ENTRY",
            entity_id=journal.id, summary=f"Imported register {group['register']} as {journal.journal_number}",
            import_batch_id=batch.id, document_number=journal.document_number,
            details={"source_sha256": source["source_sha256"], "source_register": group["register"],
                "source_header_row": group["header_row"], "difference": group["difference"], "source_preserved": True})
        if post:
            post_locked_journal(db, journal=journal, user=actor)
        result["created"].append({"register": group["register"], "id": journal.id, "journal_number": journal.journal_number, "status": journal.status})
    batch.status = "IMPORTED"
    batch.success_count = len(create)
    batch.imported_rows = batch.total_rows
    batch.valid_rows = result["financial_lines"]
    batch.validated_at = now
    db.flush()
    result["batch_id"] = batch.id
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--mapping-file", type=Path, default=ROOT / "scripts/hotel_january_2026_mapping.json")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--post", action="store_true", help="Post using the app's manual journal posting/unpost flow")
    parser.add_argument("--user-id", type=int)
    parser.add_argument("--output", type=Path, default=Path("/tmp/hotel-january-seed-result.json"))
    args = parser.parse_args()
    source = read_source(args.source)
    mapping = json.loads(args.mapping_file.read_text())
    from app.core.database import SessionLocal
    with SessionLocal() as db:
        try:
            actor = resolve_actor(db, args.user_id, interactive=True) if args.apply else None
            result = seed(db, source, mapping, actor, apply=args.apply, post=args.post)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            # Write a reviewable result before commit; any file error rolls DB back.
            result["committed"] = False
            args.output.write_text(json.dumps(result, indent=2, default=str) + "\n")
            if args.apply:
                db.commit()
                result["committed"] = True
                args.output.write_text(json.dumps(result, indent=2, default=str) + "\n")
            else:
                db.rollback()
        except Exception:
            db.rollback()
            raise
    summary = {k: v for k, v in result.items() if k not in {"created", "skipped", "already_present"}}
    summary.update(already_present=len(result["already_present"]), skipped=len(result["skipped"]))
    print(json.dumps(summary, indent=2))
    print(f"Full report: {args.output}")
    print("COMMITTED journal import. Source documents, stock, AP/AR and opening balances untouched." if args.apply else "DRY RUN: no writes. Use --apply --post to import and post.")


if __name__ == "__main__":
    main()
