"""Inspect duplicate invoices by posted Receiving Report; optionally delete exact unused drafts.

Read-only by default:
    python -m scripts.audit_receiving_invoice_duplicates
    python -m scripts.audit_receiving_invoice_duplicates --receipt-number GR-20261023-00009

After reviewing IDs and dependencies, deleting a particular set requires all
three explicit arguments (no broad delete-all operation exists):
    python -m scripts.audit_receiving_invoice_duplicates \
        --receipt-number GR-20261023-00009 --delete-id 123 --delete-id 124 --apply
"""

import argparse
from collections import defaultdict

from app.core.database import SessionLocal
from app.models.document_attachment import DocumentAttachment
from app.models.fixed_asset import FixedAsset
from app.models.general_ledger import GeneralLedger
from app.models.goods_receipt import GoodsReceipt, GoodsReceiptItem
from app.models.journal_entry import JournalEntry
from app.models.payment import PaymentAllocation
from app.models.payment_voucher import PaymentVoucherAllocation
from app.models.supplier_adjustment import SupplierAdjustment
from app.models.supplier_invoice import SupplierInvoice, SupplierInvoiceLine


def invoice_dependencies(db, invoice_id: int) -> dict[str, int]:
    return {
        "payment_allocations": db.query(PaymentAllocation).filter_by(supplier_invoice_id=invoice_id).count(),
        "voucher_allocations": db.query(PaymentVoucherAllocation).filter_by(supplier_invoice_id=invoice_id).count(),
        "adjustments": db.query(SupplierAdjustment).filter_by(supplier_invoice_id=invoice_id).count(),
        "fixed_assets": db.query(FixedAsset).filter_by(purchase_invoice_id=invoice_id).count(),
        "journals": db.query(JournalEntry).filter_by(reference_type="SUPPLIER_INVOICE", reference_id=invoice_id).count(),
        "general_ledger": db.query(GeneralLedger).filter_by(reference_type="SUPPLIER_INVOICE", reference_id=invoice_id).count(),
        "attachments": db.query(DocumentAttachment).filter_by(entity_type="SUPPLIER_INVOICE", entity_id=invoice_id).count(),
    }


def grouped_invoices(db, receipt_number: str | None):
    receipts = db.query(GoodsReceipt.id, GoodsReceipt.receipt_number)
    if receipt_number:
        receipts = receipts.filter(GoodsReceipt.receipt_number == receipt_number)
    receipt_by_id = dict(receipts.all())
    if not receipt_by_id:
        raise ValueError("Receiving Report not found")
    receipt_ids = list(receipt_by_id)
    ids = defaultdict(set)
    direct = (
        db.query(SupplierInvoice.id, SupplierInvoice.goods_receipt_id)
        .filter(SupplierInvoice.goods_receipt_id.in_(receipt_ids),
                SupplierInvoice.status.notin_(("VOID", "REJECTED")))
        .all()
    )
    for invoice_id, receipt_id in direct:
        ids[receipt_id].add(invoice_id)
    linked = (
        db.query(SupplierInvoice.id, GoodsReceiptItem.goods_receipt_id)
        .join(SupplierInvoiceLine, SupplierInvoiceLine.supplier_invoice_id == SupplierInvoice.id)
        .join(GoodsReceiptItem, GoodsReceiptItem.id == SupplierInvoiceLine.goods_receipt_item_id)
        .filter(GoodsReceiptItem.goods_receipt_id.in_(receipt_ids),
                SupplierInvoice.status.notin_(("VOID", "REJECTED")))
        .all()
    )
    for invoice_id, receipt_id in linked:
        ids[receipt_id].add(invoice_id)
    return receipt_by_id, ids


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt-number", help="Restrict the audit to a single Receiving Report")
    parser.add_argument("--delete-id", type=int, action="append", default=[], help="Explicit DRAFT invoice ID to remove")
    parser.add_argument("--apply", action="store_true", help="Commit the exact validated deletes")
    args = parser.parse_args()
    if (args.delete_id or args.apply) and not args.receipt_number:
        parser.error("Deletion requires --receipt-number, exact --delete-id values and --apply")
    if args.apply and not args.delete_id:
        parser.error("--apply requires one or more explicit --delete-id values")

    with SessionLocal() as db:
        receipt_by_id, invoice_ids = grouped_invoices(db, args.receipt_number)
        groups = {rid: sorted(ids) for rid, ids in invoice_ids.items() if len(ids) > 1}
        if args.receipt_number and not groups:
            print("No active duplicate invoices for this receipt.")
        for receipt_id, ids in sorted(groups.items()):
            print(f"RECEIVING {receipt_by_id[receipt_id]}: {len(ids)} active invoices")
            for invoice_id in ids:
                invoice = db.get(SupplierInvoice, invoice_id)
                print(f"  {invoice.id} {invoice.internal_invoice_number} {invoice.supplier_invoice_number} "
                      f"status={invoice.status} total={invoice.total_amount} dependencies={invoice_dependencies(db, invoice.id)}")
        if not args.delete_id:
            print(f"Read-only audit complete: {len(groups)} receipt(s) with multiple active invoices.")
            return

        receipt_id = next((rid for rid, num in receipt_by_id.items() if num == args.receipt_number), None)
        if args.apply:
            db.query(GoodsReceipt).filter(GoodsReceipt.id == receipt_id).with_for_update().one()
        target_ids = set(args.delete_id)
        if len(target_ids) != len(args.delete_id):
            raise ValueError("Duplicate --delete-id supplied")
        if receipt_id not in groups or not target_ids.issubset(set(groups[receipt_id])):
            raise ValueError("All target invoice IDs must be active invoices on the specified duplicate receipt")
        for invoice_id in sorted(target_ids):
            invoice = (
                db.query(SupplierInvoice).filter(SupplierInvoice.id == invoice_id)
                .populate_existing().with_for_update().one()
            )
            if invoice.status != "DRAFT":
                raise ValueError(f"Refusing deletion of non-DRAFT invoice {invoice.internal_invoice_number}")
            if any(invoice_dependencies(db, invoice.id).values()):
                raise ValueError(f"Refusing deletion of {invoice.internal_invoice_number} with downstream dependencies")
            other_receipts = (
                db.query(GoodsReceiptItem.goods_receipt_id)
                .join(SupplierInvoiceLine, SupplierInvoiceLine.goods_receipt_item_id == GoodsReceiptItem.id)
                .filter(SupplierInvoiceLine.supplier_invoice_id == invoice.id)
                .distinct().all()
            )
            if any(row.goods_receipt_id != receipt_id for row in other_receipts):
                raise ValueError(f"Refusing deletion of {invoice.internal_invoice_number} linked to another receipt")

        print(f"Validated exact DRAFT invoices for deletion: {sorted(target_ids)}")
        if not args.apply:
            print("DRY RUN: no changes written. Repeat with --apply to remove these exact IDs.")
            return
        for invoice_id in sorted(target_ids):
            db.delete(db.get(SupplierInvoice, invoice_id))
        db.commit()
        print(f"Deleted {len(target_ids)} specified unused DRAFT invoices. The Receiving Report was preserved.")


if __name__ == "__main__":
    main()
