"""Remove independently entered or imported Project Catering journals."""
import argparse
from collections import Counter
import re

MODULE_ORIGIN = re.compile(
    r"PURCHAS|INVENTORY|STOCK|RECEIV|SUPPLIER|PAYMENT|BANK_TRANSFER|"
    r"FIXED_ASSET|DEPRECIATION|OPENING|PERIOD_CLOSE|YEAR_END|POS|INVOICE|"
    r"PAYABLE|GOODS|ACCRUAL_AUTO|MARKET_LIST|MATERIAL|SALES_TRANSACTION",
    re.I,
)
CREATION_ACTIONS = {"JOURNAL_CREATED", "JOURNAL_IMPORT_CREATED"}


def independent(journal, actions):
    return (
        journal.reference_type == "MANUAL"
        and journal.reference_id == 0
        and journal.status in {"DRAFT", "VOID", "POSTED"}
        and journal.source_type in {"LIVE", "JOURNAL_IMPORT"}
        and not MODULE_ORIGIN.search(journal.document_type or "")
        and not re.match(r"^(?:GR|RR|PR|PO|SI|PAY|CPAY|POS|STK|INV|FA|BTR)-",
                         journal.document_number or "", re.I)
        and (
            "JOURNAL_IMPORT_CREATED" in actions
            or (journal.source_type == "LIVE" and "JOURNAL_CREATED" in actions)
        )
    )


def cleanup(apply):
    from sqlalchemy import MetaData, Table, inspect, select, text
    from sqlalchemy.orm import selectinload

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
            db.execute(text("LOCK TABLE journal_entries, journal_lines, general_ledger IN SHARE ROW EXCLUSIVE MODE"))
        else:
            db.execute(text("SET TRANSACTION READ ONLY"))
        unit = db.query(BusinessUnit).filter_by(name="Project Catering").one()
        journals = db.query(JournalEntry).options(selectinload(JournalEntry.lines)).filter_by(
            business_unit_id=unit.id,
        ).order_by(JournalEntry.posting_date, JournalEntry.id).all()
        ids = {j.id for j in journals}
        if not ids:
            print("No Project Catering journals found.")
            return

        provenance = {}
        for journal_id, action in db.query(AuditLog.entity_id, AuditLog.action).filter(
            AuditLog.entity_type == "JOURNAL_ENTRY",
            AuditLog.action.in_(CREATION_ACTIONS), AuditLog.entity_id.in_(ids),
        ):
            provenance.setdefault(journal_id, set()).add(action)
        candidates = {j.id: j for j in journals if independent(j, provenance.get(j.id, set()))}

        conn = db.connection()
        inspector = inspect(conn)
        schema = conn.scalar(text("SELECT current_schema()"))
        metadata = MetaData()
        linked = set()
        if candidates:
            for namespace in sorted(inspector.get_schema_names()):
                if namespace == "information_schema" or namespace.startswith("pg_"):
                    continue
                for name, foreign_keys in sorted(inspector.get_multi_foreign_keys(schema=namespace).items()):
                    table_name = name[1]
                    if namespace == schema and table_name == "journal_lines":
                        continue
                    for fk in foreign_keys:
                        if (fk["referred_table"] != "journal_entries"
                                or (fk["referred_schema"] or schema) != schema):
                            continue
                        if fk["referred_columns"] != ["id"] or len(fk["constrained_columns"]) != 1:
                            raise RuntimeError(f"Unsupported journal link in {namespace}.{table_name}")
                        table = Table(table_name, metadata, schema=namespace, autoload_with=conn)
                        if apply:
                            quoted = conn.dialect.identifier_preparer.format_table(table)
                            conn.execute(text(f"LOCK TABLE {quoted} IN SHARE ROW EXCLUSIVE MODE"))
                        column = table.c[fk["constrained_columns"][0]]
                        linked.update(conn.scalars(select(column).where(column.in_(candidates)).distinct()))

        targets = [j for j in candidates.values() if j.id not in linked]
        by_number = {j.journal_number: j for j in targets}
        ledger = db.query(GeneralLedger).filter(GeneralLedger.reference_number.in_(by_number)).all()
        for row in ledger:
            journal = by_number[row.reference_number]
            if (row.reference_type, row.reference_id) != (journal.reference_type, journal.reference_id):
                raise ValueError(f"Unexpected GL source for {journal.journal_number}")

        print(f"Project Catering, all posting dates. Eligible: {len(targets)}. "
              f"Protected or unverified: {len(journals) - len(targets)}. Linked: {len(linked)}.")
        print("Eligible by status:", dict(Counter(j.status for j in targets)))
        print("Eligible by month:", dict(sorted(Counter(j.posting_date.strftime("%Y-%m") for j in targets).items())))
        for j in targets:
            print(f"{j.id} {j.posting_date} {j.status} {j.journal_number} {j.external_reference or '-'}")
        if not apply or not targets:
            return
        for stamp in sorted({j.posting_date for j in targets}):
            FiscalPeriodService.validate_posting_date(db, stamp)
        for row in ledger:
            db.delete(row)
        for j in targets:
            ActivityService.log(
                db=db, user=None, action="JOURNAL_CATERING_CLEANUP", entity_type="JOURNAL_ENTRY",
                entity_id=j.id, summary=f"Removed independent Project Catering journal {j.journal_number}",
                document_number=j.document_number, document_status=j.status,
                details={"actor": "SYSTEM", "external_reference": j.external_reference,
                         "posting_date": j.posting_date.isoformat()},
            )
            db.delete(j)
        db.flush()
        if db.query(JournalEntry).filter(JournalEntry.id.in_([j.id for j in targets])).count():
            raise RuntimeError("Some selected journals remain")
    print(f"COMMITTED removal of {len(targets)} Project Catering journals and {len(ledger)} GL rows.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    cleanup(parser.parse_args().apply)
