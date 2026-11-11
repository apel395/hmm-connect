"""Controlled correction of manually entered historical Receiving numbers.

This changes the original recorded quantity/cost and current inventory snapshot,
not the physical movement history. All old values are retained in the audit log.
Only eligible, unconsumed, open-period records can be corrected this way.
"""

from collections import defaultdict
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import or_

from app.dependencies.authorization import is_superuser
from app.models.fixed_asset import FixedAsset
from app.models.general_ledger import GeneralLedger
from app.models.goods_receipt import GoodsReceipt
from app.models.inventory import Inventory
from app.models.journal_entry import JournalEntry
from app.models.payment import PaymentAllocation
from app.models.product import Product
from app.models.stock_movement import StockMovement
from app.models.supplier_invoice import SupplierInvoice, SupplierInvoiceLine
from app.services.activity_service import ActivityService
from app.services.fiscal_period_service import FiscalPeriodService
from app.services.goods_receipt_service import GoodsReceiptService
from app.services.location_access import enforce_location_access
from app.services.receiving_destination import line_destination
from app.services.receiving_stock_cycle import active_receipt_stock, unsafe_later_receipt_movement
from app.services.supplier_invoice_service import SupplierInvoiceService

ZERO = Decimal('0')


def correct_historical_receiving(db, receipt_id, user, data):
    try:
        return _correct(db, receipt_id, user, data)
    except Exception:
        db.rollback()
        raise


def _correct(db, receipt_id, user, data):
    if not is_superuser(user):
        raise HTTPException(403, 'Historical Receiving correction requires System Administrator')
    receipt = db.query(GoodsReceipt).filter_by(id=receipt_id).with_for_update().first()
    if not receipt:
        raise HTTPException(404, 'Receiving not found')
    enforce_location_access(user, receipt.location_id)
    if receipt.status != 'POSTED' or receipt.source_type != 'HISTORICAL_ENTRY':
        raise HTTPException(409, 'Only posted manually entered historical Receiving can use numeric correction')
    if receipt.purchase_order_id or receipt.market_list_id:
        raise HTTPException(409, 'Historical Receiving linked to PO/Market List requires source document review')

    from app.services.inventory_return_service import guard_receipt
    guard_receipt(db, receipt.id)
    FiscalPeriodService.validate_posting_date(
        db, GoodsReceiptService.business_date(receipt.received_at), system_closing=True)
    if db.query(FixedAsset.id).filter_by(goods_receipt_id=receipt.id).first():
        raise HTTPException(409, 'Receiving has linked fixed assets; correct asset records first')

    journal = GoodsReceiptService._accounting_journal(db, receipt.id)
    if not journal or journal.status != 'DRAFT':
        raise HTTPException(409, 'Receiving journal must be open DRAFT for numeric correction')
    if db.query(GeneralLedger.id).filter_by(reference_type='GOODS_RECEIPT', reference_id=receipt.id).first():
        raise HTTPException(409, 'Receiving has GL entries; Finance must correct its posted accounting first')
    from app.services.accounting_unpost import matching_ledger_rows
    if matching_ledger_rows(db, journal):
        raise HTTPException(409, 'Receiving journal has GL entries; Finance must review it first')

    ids = [item.id for item in receipt.items]
    linked_ids = db.query(SupplierInvoiceLine.supplier_invoice_id).filter(
        SupplierInvoiceLine.goods_receipt_item_id.in_(ids))
    invoices = (db.query(SupplierInvoice)
                .filter(or_(SupplierInvoice.goods_receipt_id == receipt.id,
                            SupplierInvoice.id.in_(linked_ids)),
                        SupplierInvoice.status.notin_({'VOID', 'REJECTED'}))
                .order_by(SupplierInvoice.id).with_for_update().all())
    if len(invoices) > 1:
        raise HTTPException(409, 'Multiple active invoices require Finance review')
    invoice = invoices[0] if invoices else None
    if invoice:
        if not SupplierInvoiceService.is_unconfirmed_receipt_draft(invoice, receipt):
            raise HTTPException(409, 'Only an untouched automatic invoice draft can follow historical correction')
        if (db.query(JournalEntry.id).filter_by(reference_type='SUPPLIER_INVOICE',
                                               reference_id=invoice.id)
                .filter(JournalEntry.status != 'VOID').first()
                or db.query(PaymentAllocation.id).filter_by(supplier_invoice_id=invoice.id).first()
                or Decimal(invoice.paid_amount or 0) != ZERO
                or Decimal(invoice.adjustment_amount or 0) != ZERO):
            raise HTTPException(409, 'Invoice already has financial activity; Finance must review it first')

    by_id = {item.id: item for item in receipt.items}
    changes = []
    for entry in data.items:
        item = by_id.get(entry.item_id)
        if item is None:
            raise HTTPException(422, f'Receiving line {entry.item_id} does not belong to this document')
        old_qty, old_cost = Decimal(item.quantity), Decimal(item.unit_cost)
        new_qty = Decimal(entry.quantity) if entry.quantity is not None else old_qty
        new_cost = Decimal(entry.unit_cost) if entry.unit_cost is not None else old_cost
        if old_qty == new_qty and old_cost == new_cost:
            continue
        changes.append((item, old_qty, old_cost, new_qty, new_cost))
    if not changes:
        raise HTTPException(422, 'No historical Receiving numbers changed')

    db.query(Product).filter(Product.id.in_(sorted({item.product_id for item, *_ in changes}))) \
        .order_by(Product.id).with_for_update().all()
    movements = {row.goods_receipt_item_id: row for row in active_receipt_stock(db, receipt.id)}
    deltas = defaultdict(lambda: [ZERO, ZERO, []])
    for item, old_qty, old_cost, new_qty, new_cost in changes:
        if line_destination(receipt, item) != 'WAREHOUSE':
            continue
        row = movements.get(item.id)
        if (not row or Decimal(row.quantity) != old_qty
                or Decimal(row.unit_cost) != old_cost):
            raise HTTPException(409, f'Receiving line {item.id} stock evidence differs from recorded values')
        key = (row.product_id, row.warehouse_id)
        bucket = deltas[key]
        bucket[0] += new_qty - old_qty
        bucket[1] += new_qty * new_cost - old_qty * old_cost
        bucket[2].append((row, new_qty, new_cost))

    snapshots = []
    for (product_id, warehouse_id), (qty_delta, value_delta, rows) in sorted(deltas.items()):
        stock = (db.query(Inventory)
                 .filter_by(product_id=product_id, warehouse_id=warehouse_id)
                 .with_for_update().first())
        if not stock:
            raise HTTPException(409, f'Product {product_id} has no inventory balance')
        # Hold the inventory row lock before checking later movements, so
        # another stock operation cannot change the balance mid-correction.
        if unsafe_later_receipt_movement(
                db, product_id=product_id, warehouse_id=warehouse_id,
                after_id=min(row.id for row, _, _ in rows)):
            raise HTTPException(409, f'Product {product_id} has subsequent actual stock usage or adjustment')
        before_qty = Decimal(stock.quantity)
        before_value = before_qty * Decimal(stock.average_cost)
        new_balance = before_qty + qty_delta
        new_value = before_value + value_delta
        tolerance = before_qty * Decimal('0.00005') + Decimal('0.01')
        if new_balance < ZERO or new_value < -tolerance or (new_balance == ZERO and abs(new_value) > tolerance):
            raise HTTPException(409, f'Product {product_id} cannot be safely revalued after correction')
        snapshots.append((stock, new_balance, new_value, rows))

    before_total = str(receipt.total_amount)
    for item, old_qty, old_cost, new_qty, new_cost in changes:
        item.quantity = new_qty
        item.unit_cost = new_cost
    for stock, qty, value, rows in snapshots:
        stock.quantity = qty
        stock.average_cost = value / qty if qty else ZERO
        for row, new_qty, new_cost in rows:
            # Historical numerical correction: modify the source IN, do not
            # manufacture a stock OUT/IN or GOODS_RECEIPT_UNPOST event.
            row.quantity = new_qty
            row.unit_cost = new_cost
            if row.recorded_value is not None:
                row.recorded_value = new_qty * new_cost

    GoodsReceiptService._recalculate_totals(receipt, db)
    GoodsReceiptService._sync_accounting_journal(db, receipt=receipt, user=user)
    if invoice:
        SupplierInvoiceService(db).sync_unconfirmed_receipt_draft(invoice, receipt, user)

    ActivityService.log(
        db=db, user=user, action='HISTORICAL_RECEIVING_CORRECTION',
        entity_type='GOODS_RECEIPT', entity_id=receipt.id,
        summary=f'Corrected historical values for {receipt.receipt_number}',
        before_data={'total_amount': before_total,
                     'lines': [{'id': i.id, 'quantity': str(q), 'unit_cost': str(c)}
                               for i, q, c, _, _ in changes]},
        after_data={'total_amount': str(receipt.total_amount),
                    'lines': [{'id': i.id, 'quantity': str(q), 'unit_cost': str(c)}
                              for i, _, _, q, c in changes]},
        details={'reason': data.reason.strip(), 'journal_id': journal.id,
                 'invoice_id': invoice.id if invoice else None},
    )
    db.commit()
    db.refresh(receipt)
    return receipt
