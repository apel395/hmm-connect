"""One-time, exact-ID cleanup of confirmed 27 October 2026 test invoices.

Run from the HMM Connect backend root with its production environment configured:

  PYTHONPATH=. .venv/bin/python -m scripts.cleanup_test_supplier_invoices_20261027
  PYTHONPATH=. .venv/bin/python -m scripts.cleanup_test_supplier_invoices_20261027 \
      --apply --confirm DELETE-645-658-20261027

The dry run is read-only. On apply, all changes happen in one DB transaction.
Receiving Reports, their inventory movements, and receiving journals are NEVER
deleted. Any payment, voucher, adjustment, fixed asset, attachment, unknown FK,
closed-period journal, or inconsistent journal/GL link blocks the operation.
"""

import argparse
import json
import os
import re
import tempfile
from datetime import date
from decimal import Decimal

from sqlalchemy import bindparam, text

from app.core.database import engine


EXPECTED = {invoice_id: f"INV-202610-{invoice_id - 642:04d}" for invoice_id in range(645, 659)}
EXPECTED_DATE = date(2026, 10, 27)
CONFIRMATION = "DELETE-645-658-20261027"
IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")


def rows(conn, sql, *, ids=None, **kwargs):
    statement = text(sql)
    params = dict(kwargs)
    if ids is not None:
        statement = statement.bindparams(bindparam("ids", expanding=True))
        params["ids"] = list(ids)
    return [dict(row) for row in conn.execute(statement, params).mappings().all()]


def count(conn, sql, *, ids=None, **kwargs):
    statement = text(sql)
    params = dict(kwargs)
    if ids is not None:
        statement = statement.bindparams(bindparam("ids", expanding=True))
        params["ids"] = list(ids)
    return conn.execute(statement, params).scalar_one()


def foreign_key_dependencies(conn, parent_table, parent_ids, permitted_child_tables):
    """Use production's actual FK constraints, including ones absent from models."""
    if not parent_ids:
        return []
    constraints = rows(conn, """
        SELECT c.conrelid::regclass::text AS child_table,
               a.attname AS child_column,
               cardinality(c.conkey) AS key_columns
          FROM pg_constraint c
          JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]
         WHERE c.contype = 'f'
           AND c.confrelid = to_regclass(:parent_table)
    """, parent_table=parent_table)
    blocking = []
    for constraint in constraints:
        table_name = constraint["child_table"]
        column = constraint["child_column"]
        # Schema objects are retrieved from PostgreSQL itself, but still quote
        # strictly validated identifiers before building a count statement.
        parts = table_name.split(".")
        if (constraint["key_columns"] != 1 or
                not all(IDENTIFIER.fullmatch(part) for part in parts + [column])):
            blocking.append(f"Unexpected FK shape: {table_name}.{column}")
            continue
        quoted_table = ".".join(f'"{part}"' for part in parts)
        amount = count(conn, f'SELECT count(*) FROM {quoted_table} WHERE "{column}" IN :ids', ids=parent_ids)
        if amount and parts[-1] not in permitted_child_tables:
            blocking.append(f"{table_name}.{column}: {amount} linked row(s)")
    return blocking


def audit(conn, *, lock):
    blockers = []
    ids = sorted(EXPECTED)
    invoice_rows = rows(conn, """
        SELECT id, internal_invoice_number, supplier_invoice_number, status,
               supplier_id, total_amount, paid_amount, adjustment_amount,
               payment_status, goods_receipt_id, created_at,
               (created_at AT TIME ZONE 'Asia/Jakarta')::date AS created_wib_date
          FROM supplier_invoices WHERE id IN :ids ORDER BY id
    """ + (" FOR UPDATE" if lock else ""), ids=ids)
    found = {row["id"]: row for row in invoice_rows}
    for invoice_id, expected_number in EXPECTED.items():
        row = found.get(invoice_id)
        if row is None:
            blockers.append(f"Invoice {invoice_id} is missing; no partial batch deletion")
            continue
        if row["internal_invoice_number"] != expected_number:
            blockers.append(f"Invoice {invoice_id} has unexpected number {row['internal_invoice_number']}")
        if row["created_wib_date"] != EXPECTED_DATE:
            blockers.append(f"Invoice {invoice_id} was not created on 2026-10-27 WIB")
        if row["status"] not in {"DRAFT", "VERIFIED", "POSTED", "REJECTED"}:
            blockers.append(f"Invoice {invoice_id} has unexpected status {row['status']}")
        if Decimal(row["paid_amount"] or 0) or Decimal(row["adjustment_amount"] or 0):
            blockers.append(f"Invoice {invoice_id} has payments/adjustments recorded in its balance")
        if row["payment_status"] != "UNPAID":
            blockers.append(f"Invoice {invoice_id} has payment status {row['payment_status']}")

    invoice_lines = rows(conn, """
        SELECT * FROM supplier_invoice_lines WHERE supplier_invoice_id IN :ids
        ORDER BY supplier_invoice_id, id
    """, ids=ids)
    payable_rows = rows(conn, """
        SELECT * FROM account_payables WHERE invoice_number IN :ids ORDER BY id
    """, ids=[row["internal_invoice_number"] for row in invoice_rows]) if invoice_rows else []
    payable_ids = [payable["id"] for payable in payable_rows]
    for payable in payable_rows:
        source = next((row for row in invoice_rows
                       if row["internal_invoice_number"] == payable["invoice_number"]), None)
        if source is None or payable["supplier_id"] != source["supplier_id"]:
            blockers.append(f"Unexpected legacy payable identity: {payable['id']}")
        if Decimal(payable["paid_amount"] or 0):
            blockers.append(f"Payable {payable['id']} has recorded payment amount")
        if payable["payment_status"] != "UNPAID":
            blockers.append(f"Payable {payable['id']} has payment status {payable['payment_status']}")
    line_ids = [line["id"] for line in invoice_lines]
    journal_rows = rows(conn, """
        SELECT * FROM journal_entries
         WHERE reference_type = 'SUPPLIER_INVOICE' AND reference_id IN :ids
         ORDER BY id
    """ + (" FOR UPDATE" if lock else ""), ids=ids)
    journal_ids = [journal["id"] for journal in journal_rows]
    journal_numbers = [journal["journal_number"] for journal in journal_rows]
    journal_lines = rows(conn, """
        SELECT * FROM journal_lines WHERE journal_entry_id IN :ids ORDER BY id
    """, ids=journal_ids) if journal_ids else []

    gl_rows = rows(conn, """
        SELECT * FROM general_ledger
         WHERE reference_type = 'SUPPLIER_INVOICE' AND reference_id IN :ids
         ORDER BY id
    """, ids=ids)
    gl_ids = [row["id"] for row in gl_rows]

    other_journals = rows(conn, """
        SELECT id, journal_number, reference_type, reference_id, document_number
          FROM journal_entries
         WHERE document_number IN :ids
           AND NOT (reference_type = 'SUPPLIER_INVOICE' AND reference_id BETWEEN 645 AND 658)
    """, ids=[row["internal_invoice_number"] for row in invoice_rows]) if invoice_rows else []
    if other_journals:
        blockers.append(f"Other journal sources share the test invoice numbers: {other_journals}")

    if journal_numbers:
        other_gl = rows(conn, """
            SELECT id, reference_type, reference_id, reference_number
              FROM general_ledger WHERE reference_number IN :ids
                AND NOT (reference_type = 'SUPPLIER_INVOICE' AND reference_id BETWEEN 645 AND 658)
        """, ids=journal_numbers)
        if other_gl:
            blockers.append(f"Unexpected ledger rows share journal numbers: {other_gl}")
    if journal_ids:
        closed = rows(conn, """
            SELECT j.id AS journal_id, j.journal_number, p.period_name
              FROM journal_entries j JOIN fiscal_periods p
                ON j.posting_date BETWEEN p.start_date AND p.end_date
             WHERE j.id IN :ids AND (p.is_closed = true OR p.is_open = false)
        """, ids=journal_ids)
        if closed:
            blockers.append(f"Invoice journals belong to closed accounting periods: {closed}")

    attachments = rows(conn, """
        SELECT id, entity_id, storage_provider, storage_path
          FROM document_attachments
         WHERE entity_type = 'SUPPLIER_INVOICE' AND entity_id IN :ids
    """, ids=ids)
    if attachments:
        blockers.append(f"Invoice attachments need separate storage cleanup: {attachments}")

    stock_refs = rows(conn, """
        SELECT id, reference_type, reference_id FROM stock_movements
         WHERE reference_type = 'SUPPLIER_INVOICE' AND reference_id IN :ids
    """, ids=ids)
    if stock_refs:
        blockers.append(f"Stock movements unexpectedly reference invoices: {stock_refs}")

    if line_ids:
        asset_reclass = rows(conn, """
            SELECT id, journal_number, document_type, reference_type, reference_id
              FROM journal_entries
             WHERE document_type = 'SUPPLIER_INVOICE_ASSET_RECLASS'
               AND reference_id IN :ids
        """, ids=line_ids)
        if asset_reclass:
            blockers.append(f"Asset reclassification journals reference invoice lines: {asset_reclass}")

    blockers.extend(foreign_key_dependencies(conn, "supplier_invoices", ids, {"supplier_invoice_lines"}))
    blockers.extend(foreign_key_dependencies(conn, "supplier_invoice_lines", line_ids, set()))
    blockers.extend(foreign_key_dependencies(conn, "journal_entries", journal_ids, {"journal_lines"}))
    blockers.extend(foreign_key_dependencies(conn, "account_payables", payable_ids, set()))

    # Journal/GL relationship must agree, including any unexpected GL rows
    # stored under the matching document or journal number.
    if invoice_rows:
        invoice_numbers = [row["internal_invoice_number"] for row in invoice_rows]
        extra_gl = rows(conn, """
            SELECT id, document_number, reference_type, reference_id, reference_number
              FROM general_ledger WHERE document_number IN :ids
                AND NOT (reference_type = 'SUPPLIER_INVOICE' AND reference_id BETWEEN 645 AND 658)
        """, ids=invoice_numbers)
        if extra_gl:
            blockers.append(f"Other ledger rows share invoice document numbers: {extra_gl}")
    if any(row["reference_number"] not in journal_numbers for row in gl_rows):
        blockers.append("Supplier-invoice GL rows have no corresponding invoice journal")

    snapshot = {
        "purpose": "Delete user-confirmed test invoices 645-658 created on 2026-10-27 WIB",
        "invoices": invoice_rows,
        "invoice_lines": invoice_lines,
        "account_payables": payable_rows,
        "invoice_journals": journal_rows,
        "journal_lines": journal_lines,
        "invoice_general_ledger": gl_rows,
        "blockers": blockers,
    }
    print("Target invoices:", [(r["id"], r["internal_invoice_number"], r["status"]) for r in invoice_rows])
    print("Related counts:", {
        "invoice_lines": len(invoice_lines),
        "account_payables": len(payable_rows),
        "invoice_journals": len(journal_rows),
        "journal_lines": len(journal_lines),
        "general_ledger": len(gl_rows),
    })
    if blockers:
        print("STOP: dependency or validation blockers:")
        for item in blockers:
            print("  -", item)
    else:
        print("PASS: exact 14 invoices and journal/GL dependencies validated.")
    return snapshot, blockers, journal_ids, gl_ids, payable_ids


def save_snapshot(snapshot):
    fd, path = tempfile.mkstemp(prefix="hmm_invoice_cleanup_20261027_", suffix=".json", dir="/tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(snapshot, file, default=str, indent=2, ensure_ascii=False)
    except BaseException:
        os.unlink(path)
        raise
    return path


def delete_ids(conn, table, column, ids):
    if not ids:
        return 0
    allowed = {"general_ledger", "journal_lines", "journal_entries", "supplier_invoice_lines", "supplier_invoices", "account_payables"}
    if table not in allowed or not IDENTIFIER.fullmatch(column):
        raise ValueError("Unexpected cleanup table or column")
    stmt = text(f'DELETE FROM "{table}" WHERE "{column}" IN :ids').bindparams(bindparam("ids", expanding=True))
    return conn.execute(stmt, {"ids": list(ids)}).rowcount


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Delete exact validated records in one transaction")
    parser.add_argument("--confirm", help=f"Required with --apply: {CONFIRMATION}")
    args = parser.parse_args()
    if args.apply != (args.confirm == CONFIRMATION):
        parser.error(f"--apply must be paired with --confirm {CONFIRMATION}")

    with engine.begin() as conn:
        if not args.apply:
            conn.execute(text("SET TRANSACTION READ ONLY"))
        snapshot, blockers, journal_ids, gl_ids, payable_ids = audit(conn, lock=args.apply)
        if blockers:
            raise SystemExit("No rows deleted. Resolve blockers before running --apply.")
        if not args.apply:
            print("DRY RUN complete. Nothing has been deleted.")
            return

        path = save_snapshot(snapshot)
        print("Recovery snapshot saved before deletion:", path)
        ids = sorted(EXPECTED)
        counts = {
            "general_ledger": delete_ids(conn, "general_ledger", "id", gl_ids),
            "journal_lines": delete_ids(conn, "journal_lines", "journal_entry_id", journal_ids),
            "journal_entries": delete_ids(conn, "journal_entries", "id", journal_ids),
            "supplier_invoice_lines": delete_ids(conn, "supplier_invoice_lines", "supplier_invoice_id", ids),
            "account_payables": delete_ids(conn, "account_payables", "id", payable_ids),
            "supplier_invoices": delete_ids(conn, "supplier_invoices", "id", ids),
        }
        if counts["supplier_invoices"] != len(EXPECTED):
            raise RuntimeError("Invoice deletion count mismatch. Transaction rolled back.")
        print("DELETED in one transaction:", counts)
        print("Receiving Reports, receiving journals and stock movements PRESERVED.")
    print("Committed successfully.")


if __name__ == "__main__":
    main()
