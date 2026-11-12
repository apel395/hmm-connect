"""Controlled correction of manually entered historical Receiving items.

Edited values replace their original stock IN; missing items add a genuine IN,
and nonexistent items and their original IN are removed. No compensating
OUT/return movements are manufactured. All old values remain in the audit log.
"""

from collections import defaultdict
from decimal import Decimal
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import or_

from app.dependencies.authorization import is_superuser
from app.models.fixed_asset import FixedAsset
from app.models.general_ledger import GeneralLedger
from app.models.goods_receipt import GoodsReceipt, GoodsReceiptItem
from app.models.inventory import Inventory
from app.models.journal_entry import JournalEntry
from app.models.payment import PaymentAllocation
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.warehouse import Warehouse
from app.models.stock_movement import StockMovement
from app.models.supplier_invoice import SupplierInvoice, SupplierInvoiceLine
from app.services.activity_service import ActivityService
from app.services.fiscal_period_service import FiscalPeriodService
from app.services.goods_receipt_service import GoodsReceiptService, RECEIVING_BILLING_FIELDS, STOCK_CUTOFF
from app.services.direct_coa_service import DirectCoaService
from app.services.location_access import enforce_location_access
from app.services.organization_dimensions import validate_dimensions
from app.services.receiving_destination import line_destination, receipt_destination, resolve_destination, warehouse_items
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
        raise HTTPException(409, 'Only posted manually entered historical Receiving can use administrative correction')
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

    # Only this source and its eligible derived records may change.
    editable_header = (
        'supplier_id', 'business_unit_id', 'department_id', 'location_id',
        'warehouse_id', 'received_at', 'external_reference', 'notes',
        *RECEIVING_BILLING_FIELDS,
    )
    before_header = {field: str(getattr(receipt, field)) if getattr(receipt, field) is not None else None
                     for field in editable_header}
    for field in editable_header:
        if field in data.model_fields_set:
            setattr(receipt, field, getattr(data, field))
    if not receipt.supplier_id or not db.get(Supplier, receipt.supplier_id):
        raise HTTPException(422, 'Choose a valid supplier')
    validate_dimensions(db, receipt.business_unit_id, receipt.location_id, receipt.department_id, required=True)
    if not receipt.department_id or not receipt.location_id:
        raise HTTPException(422, 'Department and location are required')
    enforce_location_access(user, receipt.location_id)
    if 'received_at' in data.model_fields_set:
        new_date = GoodsReceiptService.business_date(receipt.received_at)
        if new_date < STOCK_CUTOFF or new_date >= FiscalPeriodService.business_today():
            raise HTTPException(422, 'Historical Receiving must be dated from 2026 and before today')
        FiscalPeriodService.validate_posting_date(db, new_date, system_closing=True)
    if receipt.warehouse_id is not None:
        target_warehouse = db.get(Warehouse, receipt.warehouse_id)
        if not target_warehouse or target_warehouse.location_id != receipt.location_id:
            raise HTTPException(422, 'Warehouse must belong to the selected receiving location')
    header_changed = any(
        before_header[field] != (str(getattr(receipt, field)) if getattr(receipt, field) is not None else None)
        for field in editable_header
    )

    by_id = {item.id: item for item in receipt.items}
    removed = []
    for item_id in data.remove_item_ids:
        item = by_id.get(item_id)
        if item is None:
            raise HTTPException(422, f'Receiving line {item_id} does not belong to this document')
        removed.append(item)
    if len(removed) == len(receipt.items) and not data.add_items:
        raise HTTPException(422, 'Receiving must keep at least one item')

    changes = []
    field_updates = {}
    for entry in data.items:
        item = by_id.get(entry.item_id)
        if item is None:
            raise HTTPException(422, f'Receiving line {entry.item_id} does not belong to this document')
        old_qty, old_cost = Decimal(item.quantity), Decimal(item.unit_cost)
        new_qty = Decimal(entry.quantity) if entry.quantity is not None else old_qty
        new_cost = Decimal(entry.unit_cost) if entry.unit_cost is not None else old_cost
        old_destination = line_destination(receipt, item)
        new_destination, new_override = old_destination, item.destination_override_reason
        if 'destination_type' in entry.model_fields_set or 'destination_override_reason' in entry.model_fields_set:
            requested = entry.destination_type if 'destination_type' in entry.model_fields_set else old_destination
            reason = entry.destination_override_reason if 'destination_override_reason' in entry.model_fields_set else item.destination_override_reason
            if requested != old_destination or reason != item.destination_override_reason:
                new_destination, new_override = resolve_destination(item.product, requested, reason)
        expense = entry.expense_account_id if 'expense_account_id' in entry.model_fields_set else item.expense_account_id
        expense = expense if new_destination == 'DIRECT_USE' else None
        if new_destination == 'DIRECT_USE' and item.product.inventory_treatment != 'FIXED_ASSET':
            expense = expense or getattr(item.product, 'purchase_account_id', None)
        taxable = bool(entry.is_taxable) if 'is_taxable' in entry.model_fields_set else bool(item.is_taxable)
        rate = Decimal(entry.tax_rate or 0) if 'tax_rate' in entry.model_fields_set else Decimal(item.tax_rate or 0)
        if not taxable:
            rate = ZERO
        old_fields = (old_destination, item.destination_override_reason, item.expense_account_id,
                      bool(item.is_taxable), Decimal(item.tax_rate or 0))
        new_fields = (new_destination, new_override, expense, taxable, rate)
        if (old_qty, old_cost, old_fields) == (new_qty, new_cost, new_fields):
            continue
        changes.append((item, old_qty, old_cost, new_qty, new_cost))
        field_updates[item.id] = new_fields
    if not (changes or removed or data.add_items or header_changed):
        raise HTTPException(422, 'No historical Receiving fields changed')

    product_ids = sorted({item.product_id for item, *_ in changes} |
                         {item.product_id for item in removed} |
                         {entry.product_id for entry in data.add_items})
    products = {row.id: row for row in db.query(Product).filter(Product.id.in_(product_ids))
                .order_by(Product.id).with_for_update().all()}
    added = []
    for entry in data.add_items:
        product = products.get(entry.product_id)
        if not product or not product.is_active or product.item_type != 'BUY':
            raise HTTPException(422, f'Product {entry.product_id} is not an active buy item')
        destination, override_reason = resolve_destination(
            product, requested=entry.destination_type,
            reason=entry.destination_override_reason)
        if destination == 'WAREHOUSE' and receipt.warehouse_id is None:
            raise HTTPException(409, 'Receiving needs an existing warehouse to add stock items')
        added.append(GoodsReceiptItem(
            goods_receipt_id=receipt.id, product_id=product.id, product=product,
            destination_type=destination, destination_override_reason=override_reason,
            quantity=entry.quantity, unit_cost=entry.unit_cost,
            expense_account_id=entry.expense_account_id if destination == 'DIRECT_USE' else None,
            is_taxable=entry.is_taxable, tax_rate=entry.tax_rate if entry.is_taxable else ZERO,
        ))

    movements = {row.goods_receipt_item_id: row for row in active_receipt_stock(db, receipt.id)}
    deltas = defaultdict(lambda: [ZERO, ZERO, [], [], []])
    newly_attributed_keys = set()
    removed_stock_ids = set()

    # Retarget source IN records, never create reversal OUT/transfer movements.
    for item in list(receipt.items):
        if item in removed:
            continue
        old_destination = line_destination(receipt, item)
        old_row = movements.get(item.id)
        if old_destination == 'WAREHOUSE':
            if not old_row or Decimal(old_row.quantity) != Decimal(item.quantity) or Decimal(old_row.unit_cost) != Decimal(item.unit_cost):
                raise HTTPException(409, f'Receiving line {item.id} stock evidence differs from recorded values')
        elif old_row:
            raise HTTPException(409, f'Unexpected stock IN on Direct Use line {item.id}')
        updated = next((x for x in changes if x[0].id == item.id), None)
        new_qty = updated[3] if updated else Decimal(item.quantity)
        new_cost = updated[4] if updated else Decimal(item.unit_cost)
        new_destination = field_updates[item.id][0] if updated else old_destination
        old_key = (item.product_id, old_row.warehouse_id) if old_row else None
        new_key = (item.product_id, receipt.warehouse_id) if new_destination == 'WAREHOUSE' else None
        if new_destination == 'WAREHOUSE' and receipt.warehouse_id is None:
            raise HTTPException(422, f'Warehouse is required for item {item.product_id}')
        if old_key != new_key:
            if old_key:
                bucket = deltas[old_key]
                bucket[0] -= Decimal(item.quantity)
                bucket[1] -= Decimal(item.quantity) * Decimal(item.unit_cost)
                if not new_key:
                    bucket[3].append(old_row)
                    removed_stock_ids.add(item.id)
            if new_key:
                bucket = deltas[new_key]
                bucket[0] += new_qty
                bucket[1] += new_qty * new_cost
                newly_attributed_keys.add(new_key)
                if old_row:
                    bucket[2].append((old_row, new_qty, new_cost))
                else:
                    bucket[4].append(item)
            continue
        if old_key and (Decimal(item.quantity) != new_qty or Decimal(item.unit_cost) != new_cost):
            bucket = deltas[old_key]
            bucket[0] += new_qty - Decimal(item.quantity)
            bucket[1] += new_qty * new_cost - Decimal(item.quantity) * Decimal(item.unit_cost)
            bucket[2].append((old_row, new_qty, new_cost))

    for item in removed:
        row = movements.get(item.id)
        if line_destination(receipt, item) == 'WAREHOUSE':
            if not row or Decimal(row.quantity) != Decimal(item.quantity) or Decimal(row.unit_cost) != Decimal(item.unit_cost):
                raise HTTPException(409, f'Receiving line {item.id} stock evidence differs from recorded values')
            bucket = deltas[(row.product_id, row.warehouse_id)]
            bucket[0] -= Decimal(item.quantity)
            bucket[1] -= Decimal(item.quantity) * Decimal(item.unit_cost)
            bucket[3].append(row)
            removed_stock_ids.add(item.id)
        elif row:
            raise HTTPException(409, f'Unexpected stock movement on direct-use line {item.id}')
        if (db.query(StockMovement.id)
                .filter(StockMovement.goods_receipt_item_id == item.id,
                        StockMovement.id != (row.id if row else -1)).first()):
            raise HTTPException(409, f'Receiving line {item.id} has linked stock history; cannot delete it')

    observed_ids = [row.goods_receipt_item_id for row in active_receipt_stock(db, receipt.id)]
    if len(observed_ids) != len(set(observed_ids)):
        raise HTTPException(409, 'Receiving has duplicate original stock IN evidence')

    for item in added:
        if item.destination_type == 'WAREHOUSE':
            if receipt.warehouse_id is None:
                raise HTTPException(422, 'Warehouse is required for added stock items')
            bucket = deltas[(item.product_id, receipt.warehouse_id)]
            bucket[0] += Decimal(item.quantity)
            bucket[1] += Decimal(item.quantity) * Decimal(item.unit_cost)
            bucket[4].append(item)
            newly_attributed_keys.add((item.product_id, receipt.warehouse_id))

    snapshots = []
    for (product_id, warehouse_id), (qty_delta, value_delta, rows, removed_rows, new_lines) in sorted(deltas.items()):
        stock = GoodsReceiptService._inventory_for_update(db, product_id, warehouse_id)
        # Hold the inventory row lock before checking later movements, so
        # another stock operation cannot change the balance mid-correction.
        # For an added source line, check *all* prior stock history; its place
        # in the original movement sequence does not yet exist.
        earliest = (0 if new_lines or (product_id, warehouse_id) in newly_attributed_keys else
                    min(row.id for row, _, _ in rows) if rows else min(row.id for row in removed_rows))
        if unsafe_later_receipt_movement(
                db, product_id=product_id, warehouse_id=warehouse_id,
                after_id=earliest):
            raise HTTPException(409, f'Product {product_id} has subsequent actual stock usage or adjustment')
        before_qty = Decimal(stock.quantity)
        before_value = before_qty * Decimal(stock.average_cost)
        new_balance = before_qty + qty_delta
        new_value = before_value + value_delta
        tolerance = before_qty * Decimal('0.00005') + Decimal('0.01')
        if new_balance < ZERO or new_value < -tolerance or (new_balance == ZERO and abs(new_value) > tolerance):
            raise HTTPException(409, f'Product {product_id} cannot be safely revalued after correction')
        snapshots.append((stock, new_balance, new_value, rows, removed_rows, new_lines))

    before_total = str(receipt.total_amount)
    before_removed = [{'id': item.id, 'product_id': item.product_id,
                       'quantity': str(item.quantity), 'unit_cost': str(item.unit_cost)} for item in removed]
    for item, old_qty, old_cost, new_qty, new_cost in changes:
        item.quantity = new_qty
        item.unit_cost = new_cost
        (item.destination_type, item.destination_override_reason, item.expense_account_id,
         item.is_taxable, item.tax_rate) = field_updates[item.id]
    for item in added:
        receipt.items.append(item)
    for stock, qty, value, rows, removed_rows, new_lines in snapshots:
        stock.quantity = qty
        stock.average_cost = value / qty if qty else ZERO
        for row, new_qty, new_cost in rows:
            # Historical numerical correction: modify the source IN, do not
            # manufacture a stock OUT/IN or GOODS_RECEIPT_UNPOST event.
            row.quantity = new_qty
            row.unit_cost = new_cost
            row.warehouse_id = stock.warehouse_id
            if row.recorded_value is not None:
                row.recorded_value = new_qty * new_cost

        for row in removed_rows:
            # The mistakenly entered source never existed: remove its original
            # IN, rather than posting a compensating OUT/return.
            db.delete(row)

    if invoice:
        removed_ids = {item.id for item in removed}
        for line in list(invoice.lines):
            if line.goods_receipt_item_id in removed_ids:
                invoice.lines.remove(line)
    for item in removed:
        receipt.items.remove(item)

    GoodsReceiptService._validate_item_treatments(receipt)
    GoodsReceiptService._validate_hotel_expenses(receipt)
    receipt.destination_type = receipt_destination(receipt)
    receipt.warehouse_id = receipt.warehouse_id if warehouse_items(receipt) else None
    GoodsReceiptService._validate_destination(db, receipt, receipt.location_id)
    for row in movements.values():
        if row.goods_receipt_item_id in removed_stock_ids:
            continue
        row.business_unit_id = receipt.business_unit_id
        row.location_id = receipt.location_id
        row.department_id = receipt.department_id

    GoodsReceiptService._recalculate_totals(receipt, db)
    # New source items need IDs before the invoice lines can reference them.
    db.flush()
    new_movements = []
    for _, _, _, _, _, new_lines in snapshots:
        for item in new_lines:
            # A newly discovered historical warehouse line is a genuine new
            # source IN; no fake OUT/IN cycle for existing numerical edits.
            movement = GoodsReceiptService._movement(receipt, item, 'IN', 'GOODS_RECEIPT')
            movement.recorded_value = Decimal(item.quantity) * Decimal(item.unit_cost)
            db.add(movement)
            new_movements.append((item, movement))
    journal = GoodsReceiptService._sync_accounting_journal(db, receipt=receipt, user=user)
    resolver = DirectCoaService(db)
    for row in movements.values():
        if row.goods_receipt_item_id in removed_stock_ids:
            continue
        row.inventory_account_id = resolver.inventory_account(row.product, receipt.location_id).id
        row.offset_account_id = resolver.ap_suspense_account().id
        row.journal_entry_id = journal.id
    for item, movement in new_movements:
        movement.inventory_account_id = resolver.inventory_account(item.product, receipt.location_id).id
        movement.offset_account_id = resolver.ap_suspense_account().id
        movement.journal_entry_id = journal.id
    if invoice:
        invoice.supplier_id = receipt.supplier_id
        # A real supplier invoice number is a financial confirmation: keep
        # the placeholder until the administrator explicitly supplies one.
        if receipt.supplier_invoice_number and receipt.supplier_invoice_number.strip():
            invoice.supplier_invoice_number = receipt.supplier_invoice_number.strip()
        invoice.discount_amount = receipt.discount_amount
        invoice.business_unit_id = receipt.business_unit_id
        invoice.location_id = receipt.location_id
        invoice.department_id = receipt.department_id
        invoice.received_date = GoodsReceiptService.business_date(receipt.received_at)
        invoice.invoice_date = receipt.supplier_invoice_date or invoice.received_date
        invoice.due_date = receipt.supplier_invoice_due_date or (invoice.invoice_date + timedelta(days=30))
        for field in ('supplier_document_total', 'tax_invoice_number', 'tax_invoice_date',
                      'supplier_document_url', 'shipping_fee_amount', 'admin_fee_amount',
                      'other_fee_amount', 'other_fee_description', 'shipping_fee_account_id',
                      'admin_fee_account_id', 'other_fee_account_id'):
            setattr(invoice, field, getattr(receipt, field))
        for item in added:
            line = SupplierInvoiceLine(
                product_id=item.product_id, product=item.product, goods_receipt_item_id=item.id,
                description=item.product.name, quantity=item.quantity, uom=item.product.uom,
                unit_price=item.unit_cost, line_amount=Decimal(item.quantity) * Decimal(item.unit_cost),
                is_taxable=bool(item.is_taxable), tax_rate=Decimal(item.tax_rate or 0),
                tax_amount=Decimal(item.tax_amount or 0), department_id=receipt.department_id)
            invoice.lines.append(line)
            resolver.snapshot_invoice_line(invoice, line)
        db.flush()
        by_invoice_item = {item.id: item for item in receipt.items}
        for line in invoice.lines:
            item = by_invoice_item[line.goods_receipt_item_id]
            line.is_taxable = bool(item.is_taxable)
            line.tax_rate = item.tax_rate
            line.tax_amount = item.tax_amount
            line.department_id = receipt.department_id
            line.account_id = None
            resolver.snapshot_invoice_line(invoice, line)
        SupplierInvoiceService(db).sync_unconfirmed_receipt_draft(invoice, receipt, user)

    ActivityService.log(
        db=db, user=user, action='HISTORICAL_RECEIVING_CORRECTION',
        entity_type='GOODS_RECEIPT', entity_id=receipt.id,
        summary=f'Edited historical receiving fields for {receipt.receipt_number}',
        before_data={'total_amount': before_total, 'header': before_header, 'removed': before_removed,
                     'lines': [{'id': i.id, 'quantity': str(q), 'unit_cost': str(c)}
                               for i, q, c, _, _ in changes]},
        after_data={'total_amount': str(receipt.total_amount),
                    'header': {field: str(getattr(receipt, field)) if getattr(receipt, field) is not None else None
                               for field in editable_header},
                    'lines': [{'id': i.id, 'quantity': str(q), 'unit_cost': str(c)}
                              for i, _, _, q, c in changes],
                    'added': [{'id': i.id, 'product_id': i.product_id,
                               'quantity': str(i.quantity), 'unit_cost': str(i.unit_cost)} for i in added],
                    'removed_item_ids': [i.id for i in removed]},
        details={'reason': data.reason.strip(), 'journal_id': journal.id,
                 'invoice_id': invoice.id if invoice else None},
    )
    db.commit()
    db.refresh(receipt)
    return receipt
