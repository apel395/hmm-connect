"""One-time, exact-ID cleanup of 25 user-confirmed test supplier invoices.

Run from the HMM Connect backend root with its production environment configured:

  PYTHONPATH=. .venv/bin/python -m scripts.cleanup_test_supplier_invoices_20261027
  PYTHONPATH=. .venv/bin/python -m scripts.cleanup_test_supplier_invoices_20261027 \
      --apply --confirm DELETE-EXACT-25-TEST-INVOICES --expected-count 25

The dry run is read-only. On apply, all changes happen in one DB transaction.
Receiving Reports, their inventory movements, and receiving journals are NEVER
deleted. Only the 25 invoice ID+number pairs below, payments allocated to them,
and vouchers exclusively linked to them are removed with AP and journal/GL.
Uncapitalized fixed assets generated solely from these invoices may also be
deleted (with their invoice acquisition movement) if they have no depreciation,
other movements or accounting activity. Other assets, attachments, unexpected
FKs, closed-period journals, or inconsistent journal/GL links block deletion.
"""

import argparse
import json
import os
import re
import tempfile
from collections import Counter
from decimal import Decimal

from sqlalchemy import bindparam, text

from app.core.database import engine


EXPECTED = {
    611: "INV-202609-0038",
    616: "INV-202609-0043",
    634: "INV-202609-0061",
    635: "INV-202609-0062",
    636: "INV-202609-0063",
    639: "INV-202609-0066",
    643: "INV-202610-0001",
    644: "INV-202610-0002",
    **{invoice_id: f"INV-202610-{invoice_id - 642:04d}" for invoice_id in range(645, 662)},
}
PRESERVE_SHARED_PAYMENT_INVOICES = set()
CONFIRMATION = "DELETE-EXACT-25-TEST-INVOICES"
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
    actual_total = count(conn, "SELECT count(*) FROM supplier_invoices")
    if actual_total != len(EXPECTED):
        blockers.append(f"The invoice set changed: database has {actual_total}, approved exact-ID set has {len(EXPECTED)}")
    ids = sorted(EXPECTED)
    invoice_rows = rows(conn, """
        SELECT id, internal_invoice_number, supplier_invoice_number, status,
               supplier_id, total_amount, paid_amount, adjustment_amount,
               payment_status, goods_receipt_id, source_type, created_at,
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
    # Payment must be removed as a whole, never partly: a single payment may
    # allocate across multiple supplier invoices or carry unrelated funding.
    target_allocations = rows(conn, """
        SELECT * FROM payment_allocations WHERE supplier_invoice_id IN :ids ORDER BY id
    """, ids=ids)
    payment_ids = {row["payment_id"] for row in target_allocations}
    if payable_ids:
        payment_ids.update(row["id"] for row in rows(conn, """
            SELECT id FROM payments WHERE account_payable_id IN :ids
        """, ids=payable_ids))
    payment_ids = sorted(payment_ids)
    payment_rows = rows(conn, """
        SELECT * FROM payments WHERE id IN :ids ORDER BY id
    """ + (" FOR UPDATE" if lock else ""), ids=payment_ids) if payment_ids else []
    if len(payment_rows) != len(payment_ids):
        blockers.append("A linked payment is missing; payment set is inconsistent")
    all_payment_allocations = rows(conn, """
        SELECT * FROM payment_allocations WHERE payment_id IN :ids ORDER BY id
    """, ids=payment_ids) if payment_ids else []
    payment_funding_lines = rows(conn, """
        SELECT * FROM payment_funding_lines WHERE payment_id IN :ids ORDER BY id
    """, ids=payment_ids) if payment_ids else []
    outside_ids = sorted({alloc["supplier_invoice_id"] for alloc in all_payment_allocations
                          if alloc["supplier_invoice_id"] not in EXPECTED})
    if not set(outside_ids).issubset(PRESERVE_SHARED_PAYMENT_INVOICES):
        blockers.append(f"Payment unexpectedly references other invoices: {outside_ids}")
    preserved_invoices = rows(conn, """
        SELECT id, internal_invoice_number, supplier_id, status, total_amount,
               paid_amount, adjustment_amount, payment_status, created_at
          FROM supplier_invoices WHERE id IN :ids ORDER BY id
    """ + (" FOR UPDATE" if lock else ""), ids=outside_ids) if outside_ids else []
    if len(preserved_invoices) != len(outside_ids):
        blockers.append("A shared-payment invoice to preserve was not found")
    preserved_payables = rows(conn, """
        SELECT * FROM account_payables WHERE invoice_number IN :ids ORDER BY id
    """, ids=[row["internal_invoice_number"] for row in preserved_invoices]) if preserved_invoices else []
    preserved_payment_plan = []
    posted_payment_ids = {row["id"] for row in payment_rows if row["status"] == "POSTED"}
    for invoice in preserved_invoices:
        paid_reversal = sum(
            (Decimal(alloc["allocated_amount"]) for alloc in all_payment_allocations
             if alloc["supplier_invoice_id"] == invoice["id"] and alloc["payment_id"] in posted_payment_ids),
            Decimal("0"),
        )
        old_paid = Decimal(invoice["paid_amount"] or 0)
        new_paid = old_paid - paid_reversal
        if new_paid < 0:
            blockers.append(f"Cannot reverse shared payment on invoice {invoice['id']}: paid balance is insufficient")
            continue
        balance = max(Decimal("0"), Decimal(invoice["total_amount"] or 0)
                      - new_paid - Decimal(invoice["adjustment_amount"] or 0))
        payment_status = ("PAID" if balance == 0 and Decimal(invoice["total_amount"] or 0) > 0
                          else "PARTIALLY_PAID" if new_paid > 0 or Decimal(invoice["adjustment_amount"] or 0) > 0
                          else "UNPAID")
        payable_matches = [row for row in preserved_payables
                           if row["invoice_number"] == invoice["internal_invoice_number"]]
        for payable in payable_matches:
            if payable["supplier_id"] != invoice["supplier_id"]:
                blockers.append(f"Preserved payable {payable['id']} has a different supplier")
        preserved_payment_plan.append({
            "invoice_id": invoice["id"], "previous_paid": old_paid,
            "reversed_amount": paid_reversal, "new_paid": new_paid,
            "new_balance": balance, "new_payment_status": payment_status,
            "payable_ids": [row["id"] for row in payable_matches],
        })

    voucher_ids = {row["id"] for row in rows(conn, """
        SELECT id FROM payment_vouchers WHERE payment_id IN :ids
    """, ids=payment_ids)} if payment_ids else set()
    voucher_ids.update(row["voucher_id"] for row in rows(conn, """
        SELECT voucher_id FROM payment_voucher_allocations WHERE supplier_invoice_id IN :ids
    """, ids=ids))
    voucher_ids = sorted(voucher_ids)
    voucher_rows = rows(conn, """
        SELECT * FROM payment_vouchers WHERE id IN :ids ORDER BY id
    """ + (" FOR UPDATE" if lock else ""), ids=voucher_ids) if voucher_ids else []
    if len(voucher_rows) != len(voucher_ids):
        blockers.append("A linked payment voucher is missing; voucher set is inconsistent")
    all_voucher_allocations = rows(conn, """
        SELECT * FROM payment_voucher_allocations WHERE voucher_id IN :ids ORDER BY id
    """, ids=voucher_ids) if voucher_ids else []
    for alloc in all_voucher_allocations:
        if alloc["supplier_invoice_id"] not in EXPECTED and alloc["supplier_invoice_id"] not in PRESERVE_SHARED_PAYMENT_INVOICES:
            blockers.append(f"Voucher {alloc['voucher_id']} also contains invoice {alloc['supplier_invoice_id']} outside test set")
    for voucher in voucher_rows:
        if voucher["payment_id"] is not None and voucher["payment_id"] not in payment_ids:
            blockers.append(f"Voucher {voucher['id']} is linked to payment {voucher['payment_id']} outside test set")
    line_ids = [line["id"] for line in invoice_lines]
    invoice_by_id = {row["id"]: row for row in invoice_rows}
    line_by_id = {row["id"]: row for row in invoice_lines}
    # Invoice posting may have auto-registered a fixed asset. Only purge an
    # uncapitalized invoice-generated asset with no independent downstream use.
    # Receiving-backed and already-capitalized assets must remain untouched.
    asset_rows = rows(conn, """
        SELECT * FROM fixed_assets
         WHERE purchase_invoice_id IN :ids
            OR source_invoice_line_id IN (
                SELECT id FROM supplier_invoice_lines WHERE supplier_invoice_id IN :ids
            )
         ORDER BY id
    """ + (" FOR UPDATE" if lock else ""), ids=ids)
    asset_ids = [asset["id"] for asset in asset_rows]
    asset_movements = rows(conn, """
        SELECT * FROM fixed_asset_movements WHERE fixed_asset_id IN :ids ORDER BY id
    """, ids=asset_ids) if asset_ids else []
    asset_schedules = rows(conn, """
        SELECT * FROM fixed_asset_depreciation_schedules WHERE fixed_asset_id IN :ids ORDER BY id
    """, ids=asset_ids) if asset_ids else []
    if len(asset_rows) > 1:
        blockers.append(f"Expected at most one invoice-generated asset, found {len(asset_rows)}")
    for asset in asset_rows:
        invoice = invoice_by_id.get(asset["purchase_invoice_id"])
        line = line_by_id.get(asset["source_invoice_line_id"])
        if not invoice or not line or line["supplier_invoice_id"] != invoice["id"]:
            blockers.append(f"Fixed asset {asset['id']} links to an unexpected invoice or invoice line")
            continue
        if asset["source_type"] != "SUPPLIER_INVOICE" or asset["external_reference"] != invoice["internal_invoice_number"]:
            blockers.append(f"Fixed asset {asset['id']} is not exclusively sourced from test invoice {invoice['id']}")
        if asset["status"] not in {"DRAFT", "PENDING_SETUP", "SOURCE_UNPOSTED"}:
            blockers.append(f"Fixed asset {asset['id']} has registered status {asset['status']}")
        if (asset["goods_receipt_id"] is not None or asset["capitalization_date"] is not None
                or asset["depreciation_start_date"] is not None
                or Decimal(asset["accumulated_depreciation"] or 0) != 0
                or asset["disposed_at"] is not None or asset["written_off_at"] is not None):
            blockers.append(f"Fixed asset {asset['id']} has receipt/capitalization/depreciation/disposal history")
        movements = [move for move in asset_movements if move["fixed_asset_id"] == asset["id"]]
        if (len(movements) != 1 or movements[0]["movement_type"] != "ACQUISITION"
                or movements[0]["journal_entry_id"] is not None
                or movements[0]["reference_number"] != invoice["internal_invoice_number"]):
            blockers.append(f"Fixed asset {asset['id']} has movements beyond its invoice acquisition")
        if any(s["fixed_asset_id"] == asset["id"] for s in asset_schedules):
            blockers.append(f"Fixed asset {asset['id']} has depreciation schedules")
    if asset_rows:
        asset_journals = rows(conn, """
            SELECT id, journal_number, reference_type, reference_id, document_number
              FROM journal_entries
             WHERE document_type = 'FIXED_ASSET' AND document_number IN :ids
        """, ids=[asset["asset_number"] for asset in asset_rows])
        asset_gl = rows(conn, """
            SELECT id, reference_type, reference_id, document_number
              FROM general_ledger WHERE document_number IN :ids
        """, ids=[asset["asset_number"] for asset in asset_rows])
        if asset_journals or asset_gl:
            blockers.append(f"Fixed assets have accounting journals/GL: {asset_journals}, {asset_gl}")
        blockers.extend(foreign_key_dependencies(conn, "fixed_assets", asset_ids, {
            "fixed_asset_movements", "fixed_asset_depreciation_schedules",
        }))
        blockers.extend(foreign_key_dependencies(
            conn, "fixed_asset_movements", [move["id"] for move in asset_movements], set()
        ))
    adjustment_rows = rows(conn, """
        SELECT * FROM supplier_adjustments WHERE supplier_invoice_id IN :ids ORDER BY id
    """, ids=ids)
    adjustment_ids = [row["id"] for row in adjustment_rows]
    invoice_journals = rows(conn, """
        SELECT * FROM journal_entries
         WHERE reference_type = 'SUPPLIER_INVOICE' AND reference_id IN :ids
         ORDER BY id
    """ + (" FOR UPDATE" if lock else ""), ids=ids)
    payment_journals = rows(conn, """
        SELECT * FROM journal_entries
         WHERE reference_type = 'SUPPLIER_PAYMENT' AND reference_id IN :ids
         ORDER BY id
    """ + (" FOR UPDATE" if lock else ""), ids=payment_ids) if payment_ids else []
    adjustment_journals = rows(conn, """
        SELECT * FROM journal_entries
         WHERE reference_type = 'SUPPLIER_ADJUSTMENT' AND reference_id IN :ids
         ORDER BY id
    """ + (" FOR UPDATE" if lock else ""), ids=adjustment_ids) if adjustment_ids else []
    adjustment_journal_by_id = {row["id"]: row for row in adjustment_journals}
    for adjustment in adjustment_rows:
        linked_id = adjustment["journal_entry_id"]
        if linked_id is not None and (linked_id not in adjustment_journal_by_id or
                                      adjustment_journal_by_id[linked_id]["reference_id"] != adjustment["id"]):
            blockers.append(f"Adjustment {adjustment['id']} has an unexpected journal: {linked_id}")
    journal_rows = invoice_journals + payment_journals + adjustment_journals
    journal_ids = [journal["id"] for journal in journal_rows]
    journal_numbers = [journal["journal_number"] for journal in journal_rows]
    payment_journal_by_id = {journal["id"]: journal for journal in payment_journals}
    for payment in payment_rows:
        linked_id = payment["journal_entry_id"]
        if linked_id is not None and (linked_id not in payment_journal_by_id or
                                      payment_journal_by_id[linked_id]["reference_id"] != payment["id"]):
            blockers.append(f"Payment {payment['id']} has an unexpected journal link: {linked_id}")
    if journal_ids:
        journal_linked_payments = rows(conn, """
            SELECT id, journal_entry_id FROM payments WHERE journal_entry_id IN :ids
        """, ids=journal_ids)
        for payment in journal_linked_payments:
            if payment["id"] not in payment_ids:
                blockers.append(f"A payment outside the test set references journal {payment['journal_entry_id']}")
    journal_lines = rows(conn, """
        SELECT * FROM journal_lines WHERE journal_entry_id IN :ids ORDER BY id
    """, ids=journal_ids) if journal_ids else []

    invoice_gl = rows(conn, """
        SELECT * FROM general_ledger
         WHERE reference_type = 'SUPPLIER_INVOICE' AND reference_id IN :ids
         ORDER BY id
    """, ids=ids)
    payment_gl = rows(conn, """
        SELECT * FROM general_ledger
         WHERE reference_type = 'SUPPLIER_PAYMENT' AND reference_id IN :ids
         ORDER BY id
    """, ids=payment_ids) if payment_ids else []
    adjustment_gl = rows(conn, """
        SELECT * FROM general_ledger
         WHERE reference_type = 'SUPPLIER_ADJUSTMENT' AND reference_id IN :ids
         ORDER BY id
    """, ids=adjustment_ids) if adjustment_ids else []
    gl_rows = invoice_gl + payment_gl + adjustment_gl
    gl_ids = [row["id"] for row in gl_rows]

    other_journals = rows(conn, """
        SELECT id, journal_number, reference_type, reference_id, document_number
          FROM journal_entries
         WHERE document_number IN :ids
    """, ids=[row["internal_invoice_number"] for row in invoice_rows]) if invoice_rows else []
    known_journal_ids = {row["id"] for row in journal_rows}
    other_journals = [row for row in other_journals if row["id"] not in known_journal_ids]
    if other_journals:
        blockers.append(f"Other journal sources share the test invoice numbers: {other_journals}")

    if payment_rows:
        other_payment_journals = rows(conn, """
            SELECT id, journal_number, reference_type, reference_id, document_number
              FROM journal_entries WHERE document_number IN :ids
        """, ids=[row["payment_number"] for row in payment_rows])
        known_journal_ids = {row["id"] for row in journal_rows}
        other_payment_journals = [row for row in other_payment_journals if row["id"] not in known_journal_ids]
        if other_payment_journals:
            blockers.append(f"Other journals share the payment numbers: {other_payment_journals}")
    if adjustment_rows:
        other_adjustment_journals = rows(conn, """
            SELECT id, journal_number, reference_type, reference_id, document_number
              FROM journal_entries WHERE document_number IN :ids
        """, ids=[row["adjustment_number"] for row in adjustment_rows])
        other_adjustment_journals = [row for row in other_adjustment_journals if row["id"] not in known_journal_ids]
        if other_adjustment_journals:
            blockers.append(f"Other journals share supplier adjustment numbers: {other_adjustment_journals}")

    if journal_numbers:
        other_gl = rows(conn, """
            SELECT id, reference_type, reference_id, reference_number
              FROM general_ledger WHERE reference_number IN :ids
        """, ids=journal_numbers)
        known_gl_ids = {row["id"] for row in gl_rows}
        other_gl = [row for row in other_gl if row["id"] not in known_gl_ids]
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
    if payment_ids:
        attachments.extend(rows(conn, """
            SELECT id, entity_id, storage_provider, storage_path
              FROM document_attachments
             WHERE entity_type IN ('SUPPLIER_PAYMENT', 'PAYMENT') AND entity_id IN :ids
        """, ids=payment_ids))
    if voucher_ids:
        attachments.extend(rows(conn, """
            SELECT id, entity_id, storage_provider, storage_path
              FROM document_attachments
             WHERE entity_type = 'PAYMENT_VOUCHER' AND entity_id IN :ids
        """, ids=voucher_ids))
    if adjustment_ids:
        attachments.extend(rows(conn, """
            SELECT id, entity_id, storage_provider, storage_path
              FROM document_attachments
             WHERE entity_type = 'SUPPLIER_ADJUSTMENT' AND entity_id IN :ids
        """, ids=adjustment_ids))
    if attachments:
        blockers.append(f"Invoice attachments need separate storage cleanup: {attachments}")

    stock_refs = rows(conn, """
        SELECT id, reference_type, reference_id FROM stock_movements
         WHERE reference_type = 'SUPPLIER_INVOICE' AND reference_id IN :ids
    """, ids=ids)
    if stock_refs:
        blockers.append(f"Stock movements unexpectedly reference invoices: {stock_refs}")
    if adjustment_ids:
        adjustment_stock = rows(conn, """
            SELECT id, reference_type, reference_id FROM stock_movements
             WHERE reference_type = 'SUPPLIER_ADJUSTMENT' AND reference_id IN :ids
        """, ids=adjustment_ids)
        if adjustment_stock:
            blockers.append(f"Stock movements reference supplier adjustments: {adjustment_stock}")

    if line_ids:
        asset_reclass = rows(conn, """
            SELECT id, journal_number, document_type, reference_type, reference_id
              FROM journal_entries
             WHERE document_type = 'SUPPLIER_INVOICE_ASSET_RECLASS'
               AND reference_id IN :ids
        """, ids=line_ids)
        if asset_reclass:
            blockers.append(f"Asset reclassification journals reference invoice lines: {asset_reclass}")

    blockers.extend(foreign_key_dependencies(conn, "supplier_invoices", ids, {
        "supplier_invoice_lines", "payment_allocations", "payment_voucher_allocations", "supplier_adjustments",
        "fixed_assets",
    }))
    blockers.extend(foreign_key_dependencies(conn, "supplier_invoice_lines", line_ids, {"fixed_assets"}))
    blockers.extend(foreign_key_dependencies(conn, "journal_entries", journal_ids, {
        "journal_lines", "payments", "supplier_adjustments",
    }))
    blockers.extend(foreign_key_dependencies(conn, "journal_lines", [line["id"] for line in journal_lines], set()))
    blockers.extend(foreign_key_dependencies(conn, "account_payables", payable_ids, {"payments"}))
    blockers.extend(foreign_key_dependencies(conn, "payments", payment_ids, {
        "payment_allocations", "payment_funding_lines", "payment_vouchers",
    }))
    blockers.extend(foreign_key_dependencies(conn, "payment_vouchers", voucher_ids, {"payment_voucher_allocations"}))
    blockers.extend(foreign_key_dependencies(conn, "supplier_adjustments", adjustment_ids, set()))

    # Journal/GL relationship must agree, including any unexpected GL rows
    # stored under the matching document or journal number.
    if invoice_rows:
        invoice_numbers = [row["internal_invoice_number"] for row in invoice_rows]
        extra_gl = rows(conn, """
            SELECT id, document_number, reference_type, reference_id, reference_number
              FROM general_ledger WHERE document_number IN :ids
        """, ids=invoice_numbers)
        extra_gl = [row for row in extra_gl if row["id"] not in gl_ids]
        if extra_gl:
            blockers.append(f"Other ledger rows share invoice document numbers: {extra_gl}")
    if payment_rows:
        payment_numbers = [row["payment_number"] for row in payment_rows]
        unexpected_payment_gl = rows(conn, """
            SELECT id, document_number, reference_type, reference_id, reference_number
              FROM general_ledger WHERE document_number IN :ids
        """, ids=payment_numbers)
        unexpected_payment_gl = [row for row in unexpected_payment_gl if row["id"] not in gl_ids]
        if unexpected_payment_gl:
            blockers.append(f"Unexpected ledger rows share payment document numbers: {unexpected_payment_gl}")
    if adjustment_rows:
        unexpected_adjustment_gl = rows(conn, """
            SELECT id, document_number, reference_type, reference_id, reference_number
              FROM general_ledger WHERE document_number IN :ids
        """, ids=[row["adjustment_number"] for row in adjustment_rows])
        unexpected_adjustment_gl = [row for row in unexpected_adjustment_gl if row["id"] not in gl_ids]
        if unexpected_adjustment_gl:
            blockers.append(f"Unexpected ledger rows share adjustment document numbers: {unexpected_adjustment_gl}")
    if any(row["reference_number"] not in journal_numbers for row in gl_rows):
        blockers.append("Invoice/payment GL rows have no corresponding source journal")

    notifications = rows(conn, """
        SELECT * FROM notifications
         WHERE reference_type = 'SUPPLIER_INVOICE' AND reference_id IN :ids
    """, ids=ids)
    if payment_ids:
        notifications.extend(rows(conn, """
            SELECT * FROM notifications
             WHERE reference_type IN ('SUPPLIER_PAYMENT', 'PAYMENT') AND reference_id IN :ids
        """, ids=payment_ids))
    if voucher_ids:
        notifications.extend(rows(conn, """
            SELECT * FROM notifications
             WHERE reference_type = 'PAYMENT_VOUCHER' AND reference_id IN :ids
        """, ids=voucher_ids))
    if adjustment_ids:
        notifications.extend(rows(conn, """
            SELECT * FROM notifications
             WHERE reference_type = 'SUPPLIER_ADJUSTMENT' AND reference_id IN :ids
        """, ids=adjustment_ids))

    snapshot = {
        "purpose": "Delete only 25 user-confirmed supplier invoice IDs and related accounting; preserve receiving and stock",
        "invoices": invoice_rows,
        "invoice_lines": invoice_lines,
        "fixed_assets": asset_rows,
        "fixed_asset_movements": asset_movements,
        "account_payables": payable_rows,
        "payments": payment_rows,
        "payment_allocations": all_payment_allocations,
        "payment_funding_lines": payment_funding_lines,
        "payment_vouchers": voucher_rows,
        "payment_voucher_allocations": all_voucher_allocations,
        "supplier_adjustments": adjustment_rows,
        "preserved_shared_payment_invoices": preserved_invoices,
        "preserved_shared_payment_payables": preserved_payables,
        "preserved_invoice_balance_changes": preserved_payment_plan,
        "invoice_and_payment_journals": journal_rows,
        "journal_lines": journal_lines,
        "invoice_and_payment_general_ledger": gl_rows,
        "notifications": notifications,
        "blockers": blockers,
    }
    print("Total supplier invoices targeted:", len(invoice_rows))
    print("Invoice statuses:", dict(Counter(row["status"] for row in invoice_rows)))
    print("Invoice source types:", dict(Counter(row["source_type"] for row in invoice_rows)))
    print("Invoices without a direct Receiving Report link:",
          sum(row["goods_receipt_id"] is None for row in invoice_rows))
    print("First 20:", [(r["id"], r["internal_invoice_number"], r["status"]) for r in invoice_rows[:20]])
    print("Last 20:", [(r["id"], r["internal_invoice_number"], r["status"]) for r in invoice_rows[-20:]])
    print("Related counts:", {
        "invoice_lines": len(invoice_lines),
        "fixed_assets": len(asset_rows),
        "fixed_asset_movements": len(asset_movements),
        "account_payables": len(payable_rows),
        "payments": len(payment_rows),
        "payment_allocations": len(all_payment_allocations),
        "payment_funding_lines": len(payment_funding_lines),
        "payment_vouchers": len(voucher_rows),
        "payment_voucher_allocations": len(all_voucher_allocations),
        "supplier_adjustments": len(adjustment_rows),
        "invoice_and_payment_journals": len(journal_rows),
        "journal_lines": len(journal_lines),
        "general_ledger": len(gl_rows),
        "notifications": len(notifications),
    })
    if asset_rows:
        print("Invoice-generated fixed assets:", [
            (asset["id"], asset["asset_number"], asset["source_type"], asset["status"],
             asset["purchase_invoice_id"], asset["source_invoice_line_id"])
            for asset in asset_rows
        ])
    if preserved_payment_plan:
        print("Preserved invoices to rebalance after removing shared test payments:")
        for plan in preserved_payment_plan:
            print(" ", plan["invoice_id"], "reverse", plan["reversed_amount"],
                  "paid", plan["previous_paid"], "->", plan["new_paid"],
                  "status", plan["new_payment_status"])
    if blockers:
        print("STOP: dependency or validation blockers:")
        for item in blockers:
            print("  -", item)
    else:
        print("PASS: exact 25 invoice IDs/numbers and payment/AP/journal/GL dependencies validated.")
    return snapshot, blockers, journal_ids, gl_ids, payable_ids, payment_ids, voucher_ids, adjustment_ids, [row["id"] for row in notifications]


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
    allowed = {
        "general_ledger", "journal_lines", "journal_entries", "supplier_invoice_lines",
        "supplier_invoices", "account_payables", "payment_allocations",
        "payment_funding_lines", "payments", "payment_voucher_allocations",
        "payment_vouchers", "supplier_adjustments", "notifications",
        "fixed_asset_movements", "fixed_assets",
    }
    if table not in allowed or not IDENTIFIER.fullmatch(column):
        raise ValueError("Unexpected cleanup table or column")
    stmt = text(f'DELETE FROM "{table}" WHERE "{column}" IN :ids').bindparams(bindparam("ids", expanding=True))
    return conn.execute(stmt, {"ids": list(ids)}).rowcount


def rebalance_preserved_invoices(conn, plans):
    """Undo only deleted POSTED payments; preserve invoices 659-661 themselves."""
    for plan in plans:
        invoice_id = plan["invoice_id"]
        result = conn.execute(text("""
            UPDATE supplier_invoices
               SET paid_amount = :paid, balance_amount = :balance,
                   payment_status = :payment_status, updated_at = now()
             WHERE id = :invoice_id
        """), {
            "invoice_id": invoice_id, "paid": plan["new_paid"],
            "balance": plan["new_balance"], "payment_status": plan["new_payment_status"],
        })
        if result.rowcount != 1:
            raise RuntimeError(f"Could not rebalance preserved invoice {invoice_id}. Transaction rolled back.")
        if plan["payable_ids"]:
            stmt = text("""
                UPDATE account_payables
                   SET paid_amount = :paid, outstanding_amount = :balance,
                       payment_status = :payment_status, status = :status,
                       last_payment_date = (
                           SELECT MAX(p.payment_date)
                             FROM payment_allocations pa
                             JOIN payments p ON p.id = pa.payment_id
                            WHERE pa.supplier_invoice_id = :invoice_id AND p.status = 'POSTED'
                       ), updated_at = now()
                 WHERE id IN :ids
            """).bindparams(bindparam("ids", expanding=True))
            updated = conn.execute(stmt, {
                "ids": plan["payable_ids"], "invoice_id": invoice_id,
                "paid": plan["new_paid"], "balance": plan["new_balance"],
                "payment_status": plan["new_payment_status"],
                "status": "PAID" if plan["new_payment_status"] == "PAID" else "OPEN",
            })
            if updated.rowcount != len(plan["payable_ids"]):
                raise RuntimeError(f"Could not rebalance AP records of invoice {invoice_id}. Transaction rolled back.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Delete exact validated records in one transaction")
    parser.add_argument("--confirm", help=f"Required with --apply: {CONFIRMATION}")
    parser.add_argument("--expected-count", type=int, help="Required with --apply: invoice count from the dry run")
    args = parser.parse_args()
    if args.apply != (args.confirm == CONFIRMATION):
        parser.error(f"--apply must be paired with --confirm {CONFIRMATION}")
    if args.apply and (args.expected_count is None or args.expected_count <= 0):
        parser.error("--apply requires --expected-count from the dry run")

    with engine.begin() as conn:
        if not args.apply:
            conn.execute(text("SET TRANSACTION READ ONLY"))
        else:
            conn.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))
            conn.execute(text("SET LOCAL lock_timeout = '5s'"))
            conn.execute(text("LOCK TABLE supplier_invoices IN SHARE ROW EXCLUSIVE MODE"))
        snapshot, blockers, journal_ids, gl_ids, payable_ids, payment_ids, voucher_ids, adjustment_ids, notification_ids = audit(conn, lock=args.apply)
        if args.apply and len(EXPECTED) != args.expected_count:
            raise RuntimeError(
                f"Supplier invoice count changed: expected {args.expected_count}, found {len(EXPECTED)}. No rows deleted."
            )
        if blockers:
            raise SystemExit("No rows deleted. Resolve blockers before running --apply.")
        if not args.apply:
            print("DRY RUN complete. Nothing has been deleted.")
            return

        path = save_snapshot(snapshot)
        print("Recovery snapshot saved before deletion:", path)
        ids = sorted(EXPECTED)
        counts = {
            "notifications": delete_ids(conn, "notifications", "id", notification_ids),
            "general_ledger": delete_ids(conn, "general_ledger", "id", gl_ids),
            "journal_lines": delete_ids(conn, "journal_lines", "journal_entry_id", journal_ids),
            "fixed_asset_movements": delete_ids(
                conn, "fixed_asset_movements", "fixed_asset_id", [asset["id"] for asset in snapshot["fixed_assets"]]
            ),
            "fixed_assets": delete_ids(conn, "fixed_assets", "id", [asset["id"] for asset in snapshot["fixed_assets"]]),
            "payment_voucher_allocations": delete_ids(conn, "payment_voucher_allocations", "voucher_id", voucher_ids),
            "payment_vouchers": delete_ids(conn, "payment_vouchers", "id", voucher_ids),
            "payment_allocations": delete_ids(conn, "payment_allocations", "payment_id", payment_ids),
            "payment_funding_lines": delete_ids(conn, "payment_funding_lines", "payment_id", payment_ids),
            "payments": delete_ids(conn, "payments", "id", payment_ids),
            "supplier_adjustments": delete_ids(conn, "supplier_adjustments", "id", adjustment_ids),
            "journal_entries": delete_ids(conn, "journal_entries", "id", journal_ids),
            "supplier_invoice_lines": delete_ids(conn, "supplier_invoice_lines", "supplier_invoice_id", ids),
            "account_payables": delete_ids(conn, "account_payables", "id", payable_ids),
            "supplier_invoices": delete_ids(conn, "supplier_invoices", "id", ids),
        }
        if counts["supplier_invoices"] != len(EXPECTED):
            raise RuntimeError("Invoice deletion count mismatch. Transaction rolled back.")
        for key, snapshot_key in {
            "notifications": "notifications",
            "general_ledger": "invoice_and_payment_general_ledger",
            "journal_lines": "journal_lines",
            "fixed_asset_movements": "fixed_asset_movements",
            "fixed_assets": "fixed_assets",
            "payment_voucher_allocations": "payment_voucher_allocations",
            "payment_vouchers": "payment_vouchers",
            "payment_allocations": "payment_allocations",
            "payment_funding_lines": "payment_funding_lines",
            "payments": "payments",
            "supplier_adjustments": "supplier_adjustments",
            "journal_entries": "invoice_and_payment_journals",
            "supplier_invoice_lines": "invoice_lines",
            "account_payables": "account_payables",
            "supplier_invoices": "invoices",
        }.items():
            if counts[key] != len(snapshot[snapshot_key]):
                raise RuntimeError(f"Deleted {counts[key]} {key} rows but audited {len(snapshot[snapshot_key])}. Rolled back.")
        rebalance_preserved_invoices(conn, snapshot["preserved_invoice_balance_changes"])
        print("DELETED in one transaction:", counts)
        print("25 specified supplier invoices cleared. Receiving Reports, their journals, and stock PRESERVED.")
    print("Committed successfully.")


if __name__ == "__main__":
    main()
