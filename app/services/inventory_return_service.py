"""Source-linked warehouse returns. No service function commits a partial event."""
from datetime import datetime, time, timezone
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import DBAPIError

from app.models.goods_receipt import GoodsReceipt, GoodsReceiptItem
from app.models.inventory import Inventory
from app.models.inventory_return import InventoryReturn, InventoryReturnItem, InventoryReplacement
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.stock_movement import StockMovement
from app.models.supplier_adjustment import SupplierAdjustment
from app.models.supplier_invoice import SupplierInvoice
from app.models.warehouse import Warehouse
from app.services.activity_service import AuditService
from app.services.direct_coa_service import DirectCoaService
from app.services.document_number import next_document_number
from app.services.document_accounting import invoice_is_accounted
from app.services.fiscal_period_service import FiscalPeriodService
from app.services.inventory_posting import post_inventory_journal
from app.services.location_access import enforce_location_access, enforce_warehouse_access
from app.services.receiving_destination import line_destination

ZERO = Decimal('0')


def money(value):
    return Decimal(value).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)


def guard_receipt(db, receipt_id):
    replacement = db.query(InventoryReplacement).join(GoodsReceiptItem,
        GoodsReceiptItem.id == InventoryReplacement.goods_receipt_item_id).filter(
            GoodsReceiptItem.goods_receipt_id == receipt_id).first()
    active = db.query(InventoryReturn).filter(InventoryReturn.goods_receipt_id == receipt_id,
                                            ((InventoryReturn.status != 'VOID') | InventoryReturn.journal_entry_id.is_not(None))).first()
    if active or replacement:
        raise HTTPException(409, 'Receiving is linked to an inventory return/replacement; preserve its source quantities and accounting')


def guard_invoice(db, invoice_id):
    if db.query(InventoryReturn).filter(InventoryReturn.status == 'POSTED', InventoryReturn.supplier_invoice_id == invoice_id,
                                       InventoryReturn.credit_journal_id.is_not(None)).first():
        raise HTTPException(409, 'Invoice has a settled inventory return credit; reverse the return before correcting the invoice')
    from app.models.inventory_return import InventoryReturnEvent
    from sqlalchemy.orm import aliased
    reversal = aliased(InventoryReturnEvent)
    if db.query(InventoryReturnEvent).outerjoin(reversal, reversal.reverses_event_id == InventoryReturnEvent.id).filter(
            InventoryReturnEvent.supplier_invoice_id == invoice_id, InventoryReturnEvent.kind == 'APPLY', reversal.id.is_(None)).first():
        raise HTTPException(409, 'Reverse supplier credit applications before correcting the invoice')


def account(db, account_id, kind='ASSET'):
    value = DirectCoaService(db).account(account_id, 'Inventory return account')
    if value.account_type != kind or value.normal_balance != 'DEBIT':
        raise HTTPException(422, f'Return account must be a debit-balance {kind} posting account')
    if kind == 'ASSET' and value.account_subtype in DirectCoaService.BANK_SUBTYPES:
        raise HTTPException(422, 'Use a non-cash asset account for supplier return/credit clearing')
    return value


def receipt(db, receipt_id, user):
    row = db.query(GoodsReceipt).filter(GoodsReceipt.id == receipt_id).with_for_update().first()
    if not row:
        raise HTTPException(404, 'Receiving not found')
    enforce_location_access(user, row.location_id)
    warehouse = db.get(Warehouse, row.warehouse_id) if row.warehouse_id else None
    if not warehouse or not warehouse.is_active:
        raise HTTPException(409, 'An active source warehouse is required')
    enforce_warehouse_access(user, warehouse)
    if row.status != 'POSTED' or row.source_type == 'SUPPLIER_REPLACEMENT':
        raise HTTPException(409, 'Select an original posted purchasing Receiving')
    if not row.supplier_id or not row.business_unit_id or not row.department_id or not row.location_id:
        raise HTTPException(409, 'Source Receiving requires supplier and organization dimensions')
    return row


def returned_quantities(db, receipt_id):
    return dict(db.query(InventoryReturnItem.goods_receipt_item_id, func.sum(InventoryReturnItem.quantity))
        .join(InventoryReturn).filter(InventoryReturn.goods_receipt_id == receipt_id,
                                     InventoryReturn.status == 'POSTED')
        .group_by(InventoryReturnItem.goods_receipt_item_id).all())


def source_lines(db, source):
    used = returned_quantities(db, source.id)
    inventory = {row.product_id: row for row in db.query(Inventory).filter(Inventory.warehouse_id == source.warehouse_id)}
    return [{'id': line.id, 'product_id': line.product_id, 'code': line.product.code,
             'name': line.product.name, 'uom': line.product.uom, 'received': line.quantity,
             'returned': used.get(line.id, ZERO), 'remaining': max(ZERO, Decimal(line.quantity) - Decimal(used.get(line.id, ZERO))),
             'available': inventory[line.product_id].quantity if line.product_id in inventory else ZERO}
            for line in source.items if line_destination(source, line) == 'WAREHOUSE']


def get_return(db, document_id, user):
    # Lock the common receipt before each return, serializing returns of the same receipt.
    source_id = db.query(InventoryReturn.goods_receipt_id).filter(InventoryReturn.id == document_id).scalar()
    if not source_id:
        raise HTTPException(404, 'Inventory return not found')
    source = receipt(db, source_id, user)
    row = db.query(InventoryReturn).filter(InventoryReturn.id == document_id).with_for_update().one()
    return row, source


def create_return(db, data, user):
    source = receipt(db, data.goods_receipt_id, user)
    existing = db.query(InventoryReturn).filter(InventoryReturn.request_key == str(data.request_key)).first()
    if existing:
        same = existing.goods_receipt_id == source.id and existing.purpose == data.purpose and existing.return_date == data.return_date and existing.reason == data.reason.strip() and existing.clearing_account_id == data.clearing_account_id
        same = same and sorted((line.goods_receipt_item_id, Decimal(line.quantity)) for line in existing.items) == sorted((line.goods_receipt_item_id, Decimal(line.quantity)) for line in data.items)
        if not same:
            raise HTTPException(409, 'Return request key was already used for a different document; refresh before retrying')
        return existing
    if not data.reason.strip():
        raise HTTPException(422, 'Enter the return reason')
    FiscalPeriodService.validate_posting_date(db, data.return_date)
    source_date = source.received_at.astimezone(ZoneInfo("Asia/Jakarta")).date() if source.received_at.tzinfo else source.received_at.date()
    if data.return_date < source_date:
        raise HTTPException(422, 'Return date cannot precede Receiving')
    account(db, data.clearing_account_id)
    remaining = {line['id']: line for line in source_lines(db, source)}
    seen = set()
    for incoming in data.items:
        line = remaining.get(incoming.goods_receipt_item_id)
        if not line or incoming.goods_receipt_item_id in seen:
            raise HTTPException(422, 'Select distinct warehouse lines from this Receiving')
        if incoming.quantity > line['remaining'] or incoming.quantity > line['available']:
            raise HTTPException(409, f'Return quantity exceeds received/available stock for {line["code"]}')
        seen.add(incoming.goods_receipt_item_id)
    row = InventoryReturn(request_key=str(data.request_key), number=next_document_number(db, 'RTN'), goods_receipt_id=source.id,
        purpose=data.purpose, status='DRAFT', return_date=data.return_date, reason=data.reason.strip(),
        clearing_account_id=data.clearing_account_id, created_by_id=user.id)
    row.items = [InventoryReturnItem(goods_receipt_item_id=line.goods_receipt_item_id, quantity=line.quantity, uom=remaining[line.goods_receipt_item_id]['uom']) for line in data.items]
    db.add(row)
    db.flush()
    audit(db, row, user, 'CREATE')
    return row


def journal(db, row, source, user, posting_date, reference_type, reference_id, number, entries):
    result = JournalEntry(journal_number=next_document_number(db, 'JV', digits=6), posting_date=posting_date,
        status='DRAFT', document_type=reference_type, document_number=number, reference_type=reference_type,
        reference_id=reference_id, description=f'{reference_type}: {row.number}', created_by_id=user.id,
        business_unit_id=source.business_unit_id, department_id=source.department_id, location_id=source.location_id)
    result.lines = [JournalLine(line_number=index, account_id=coa, debit=debit, credit=credit,
        description=row.reason, supplier_id=source.supplier_id, business_unit_id=source.business_unit_id,
        department_id=source.department_id, location_id=source.location_id)
        for index, (coa, debit, credit) in enumerate(entries, 1) if debit or credit]
    db.add(result)
    db.flush()
    post_inventory_journal(db, result, user)
    return result


def audit(db, row, user, action, details=None):
    AuditService.log(db=db, user=user, action=action, entity_type='INVENTORY_RETURN', entity_id=row.id,
        summary=f'{action} {row.number}', document_type='INVENTORY_RETURN', document_number=row.number,
        document_status=row.status, details=details or {})


def post_return(db, document_id, user):
    row, source = get_return(db, document_id, user)
    if row.status != 'DRAFT':
        raise HTTPException(409, 'Only a draft return can be posted')
    FiscalPeriodService.validate_posting_date(db, row.return_date)
    clearing = account(db, row.clearing_account_id)
    used = returned_quantities(db, source.id)
    prepared = []
    inventory_rows = {}
    # One deterministic lock per product, including repeated products in source lines.
    for product_id in sorted({line.receipt_item.product_id for line in row.items}):
        inventory_rows[product_id] = db.query(Inventory).filter(Inventory.product_id == product_id,
            Inventory.warehouse_id == source.warehouse_id).with_for_update().first()
    requested = {}
    for line in row.items:
        original = line.receipt_item
        if original.goods_receipt_id != source.id or line_destination(source, original) != 'WAREHOUSE':
            raise HTTPException(409, 'Return line is no longer an eligible source warehouse line')
        if line.quantity > Decimal(original.quantity) - Decimal(used.get(original.id, ZERO)):
            raise HTTPException(409, 'Other posted returns have consumed this source quantity')
        inventory = inventory_rows[original.product_id]
        requested[original.product_id] = requested.get(original.product_id, ZERO) + line.quantity
        if not inventory or requested[original.product_id] > Decimal(inventory.quantity):
            raise HTTPException(409, f'Insufficient stock for {original.product.code}')
        cost = Decimal(inventory.average_cost or 0)
        if cost <= ZERO:
            raise HTTPException(409, 'Positive warehouse carrying cost is required')
        source_movement = db.query(StockMovement).filter(StockMovement.goods_receipt_id == source.id,
            StockMovement.goods_receipt_item_id == original.id, StockMovement.reference_type == 'GOODS_RECEIPT',
            StockMovement.movement_type == 'IN').order_by(StockMovement.id.desc()).first()
        coa = (DirectCoaService(db).account(source_movement.inventory_account_id, 'Source inventory')
               if source_movement and source_movement.inventory_account_id else DirectCoaService(db).inventory_account(original.product))
        if coa.account_type != 'ASSET' or coa.normal_balance != 'DEBIT' or coa.id == clearing.id or coa.account_subtype in DirectCoaService.BANK_SUBTYPES:
            raise HTTPException(422, 'Clearing must differ from the source inventory asset account')
        prepared.append((line, inventory, cost, coa.id, money(line.quantity * cost)))
    row.total_cost = sum((line[4] for line in prepared), ZERO)
    entry = journal(db, row, source, user, row.return_date, 'SUPPLIER_RETURN', row.id, row.number,
                    [(clearing.id, row.total_cost, ZERO)] + [(coa, ZERO, amount) for _, _, _, coa, amount in prepared])
    for line, inventory, cost, coa, amount in prepared:
        line.unit_cost, line.line_cost, line.inventory_account_id = cost, amount, coa
        inventory.quantity = Decimal(inventory.quantity) - line.quantity
        db.add(StockMovement(product_id=line.receipt_item.product_id, warehouse_id=source.warehouse_id,
            business_unit_id=source.business_unit_id, department_id=source.department_id, location_id=source.location_id,
            movement_type='OUT', quantity=-line.quantity, unit_cost=cost, recorded_value=amount, reference_type='SUPPLIER_RETURN',
            reference_id=row.id, goods_receipt_id=source.id, goods_receipt_item_id=line.goods_receipt_item_id,
            inventory_account_id=coa, offset_account_id=clearing.id, journal_entry_id=entry.id,
            created_at=datetime.combine(row.return_date, time(), tzinfo=timezone.utc), notes=f'{row.number} / {source.receipt_number}'))
    row.status, row.journal_entry_id, row.posted_at = 'POSTED', entry.id, datetime.now(timezone.utc)
    audit(db, row, user, 'POST', {'carrying_cost': str(row.total_cost), 'purpose': row.purpose})
    return row


def replace_goods(db, document_id, data, user):
    row, source = get_return(db, document_id, user)
    if row.status != 'POSTED' or row.purpose != 'REPLACEMENT':
        raise HTTPException(409, 'Select a posted replacement-purpose return')
    FiscalPeriodService.validate_posting_date(db, data.received_date)
    if data.received_date < row.return_date or not data.delivery_note.strip():
        raise HTTPException(422, 'Replacement date/reference is invalid')
    account(db, row.clearing_account_id)
    originals = {line.id: line for line in row.items}
    duplicate = db.query(InventoryReplacement.id).join(GoodsReceiptItem, GoodsReceiptItem.id == InventoryReplacement.goods_receipt_item_id).join(GoodsReceipt, GoodsReceipt.id == GoodsReceiptItem.goods_receipt_id).filter(InventoryReplacement.return_item_id.in_(originals), func.lower(GoodsReceipt.delivery_note_number) == data.delivery_note.strip().lower()).first()
    if duplicate:
        raise HTTPException(409, 'This replacement delivery note is already registered for the return')
    previous = dict(db.query(InventoryReplacement.return_item_id, func.sum(InventoryReplacement.quantity))
                    .filter(InventoryReplacement.return_item_id.in_(originals)).group_by(InventoryReplacement.return_item_id))
    prior_values = dict(db.query(InventoryReplacement.return_item_id, func.sum(GoodsReceiptItem.replacement_line_value)).join(GoodsReceiptItem, GoodsReceiptItem.id == InventoryReplacement.goods_receipt_item_id).filter(InventoryReplacement.return_item_id.in_(originals)).group_by(InventoryReplacement.return_item_id))
    prepared, seen = [], set()
    for incoming in data.items:
        line = originals.get(incoming.return_item_id)
        if not line or line.id in seen or incoming.quantity > line.quantity - Decimal(previous.get(line.id, ZERO)):
            raise HTTPException(409, 'Replacement exceeds remaining returned quantity')
        seen.add(line.id)
        account(db, line.inventory_account_id)
        already = Decimal(previous.get(line.id, ZERO))
        remaining_value = Decimal(line.line_cost) - Decimal(prior_values.get(line.id, ZERO))
        # Allocate the immutable return-line currency value proportionally. The final
        # replacement receives the remaining cents; no gain/loss balancing entry.
        value = remaining_value if already + incoming.quantity == line.quantity else money(Decimal(line.line_cost) * incoming.quantity / line.quantity)
        if value < ZERO or value > remaining_value:
            raise HTTPException(409, 'Replacement exceeds remaining return carrying value')
        prepared.append((line, incoming.quantity, value))
    stocks = {product_id: db.query(Inventory).filter(Inventory.product_id == product_id,
        Inventory.warehouse_id == source.warehouse_id).with_for_update().one()
        for product_id in sorted({line.receipt_item.product_id for line, _, _ in prepared})}
    replacement = GoodsReceipt(receipt_number=next_document_number(db, 'GR', digits=5, day=True), status='POSTED',
        supplier_id=source.supplier_id, received_by_id=user.id, received_at=datetime.combine(data.received_date, time(), tzinfo=timezone.utc),
        destination_type='WAREHOUSE', warehouse_id=source.warehouse_id, business_unit_id=source.business_unit_id,
        department_id=source.department_id, location_id=source.location_id, source_type='SUPPLIER_REPLACEMENT',
        delivery_note_number=data.delivery_note.strip(), notes=f'Replacement for {row.number}; no additional supplier invoice')
    for line, qty, value in prepared:
        replacement.items.append(GoodsReceiptItem(product_id=line.receipt_item.product_id, quantity=qty,
            unit_cost=line.unit_cost, replacement_line_value=value, destination_type='WAREHOUSE', is_taxable=False, tax_rate=ZERO, tax_amount=ZERO))
    replacement.subtotal = replacement.total_amount = sum((value for _, _, value in prepared), ZERO)
    replacement.tax_amount = ZERO
    db.add(replacement)
    db.flush()
    entries = [(line.inventory_account_id, value, ZERO) for line, qty, value in prepared]
    entries.append((row.clearing_account_id, ZERO, replacement.total_amount))
    entry = journal(db, row, source, user, data.received_date, 'SUPPLIER_REPLACEMENT', replacement.id, replacement.receipt_number, entries)
    for (line, qty, value), new_line in zip(prepared, replacement.items):
        stock = stocks[line.receipt_item.product_id]
        old_quantity = Decimal(stock.quantity)
        stock.average_cost = ((old_quantity * Decimal(stock.average_cost or 0) + qty * line.unit_cost) / (old_quantity + qty)).quantize(Decimal('.0001'), rounding=ROUND_HALF_UP)
        stock.quantity = old_quantity + qty
        db.add(InventoryReplacement(return_item_id=line.id, goods_receipt_item_id=new_line.id, quantity=qty))
        db.add(StockMovement(product_id=new_line.product_id, warehouse_id=source.warehouse_id,
            business_unit_id=source.business_unit_id, department_id=source.department_id, location_id=source.location_id,
            movement_type='IN', quantity=qty, unit_cost=line.unit_cost, recorded_value=value, reference_type='SUPPLIER_REPLACEMENT',
            reference_id=replacement.id, goods_receipt_id=replacement.id, goods_receipt_item_id=new_line.id,
            inventory_account_id=line.inventory_account_id, offset_account_id=row.clearing_account_id,
            journal_entry_id=entry.id, created_at=replacement.received_at, notes=f'{replacement.receipt_number} / {row.number}'))
    audit(db, row, user, 'RECEIVE_REPLACEMENT', {'receipt_id': replacement.id, 'receipt_number': replacement.receipt_number})
    return row


def settle_credit(db, document_id, data, user):
    row, source = get_return(db, document_id, user)
    if row.status != 'POSTED' or row.purpose != 'AP_CREDIT' or row.credit_journal_id:
        raise HTTPException(409, 'Select an unsettled posted AP-credit return')
    FiscalPeriodService.validate_posting_date(db, data.credit_date)
    if data.credit_date < row.return_date or not data.credit_reference.strip():
        raise HTTPException(422, 'Credit date/reference is invalid')
    try:
        invoice = db.query(SupplierInvoice).filter(SupplierInvoice.id == data.supplier_invoice_id).with_for_update(nowait=True).first()
    except DBAPIError as error:
        if getattr(error.orig, 'pgcode', None) == '55P03' or getattr(error.orig, 'sqlstate', None) == '55P03':
            raise HTTPException(409, 'Invoice is being processed by another payment/Finance transaction; retry after it completes') from error
        raise
    if not invoice or invoice.goods_receipt_id != source.id or invoice.supplier_id != source.supplier_id or not invoice_is_accounted(db, invoice):
        raise HTTPException(409, 'Select the accounted supplier invoice linked to the source Receiving')
    if invoice.currency != 'IDR':
        raise HTTPException(422, 'Supplier return credit currently requires an IDR invoice')
    net, tax = money(data.net_amount), money(data.tax_amount)
    gross = net + tax
    previous_credit = db.query(func.coalesce(func.sum(InventoryReturn.supplier_credit), 0)).filter(
        InventoryReturn.status == 'POSTED', InventoryReturn.supplier_invoice_id == invoice.id, InventoryReturn.credit_journal_id.is_not(None)).scalar()
    if gross <= ZERO or gross > Decimal(invoice.total_amount) - Decimal(invoice.adjustment_amount or 0) - Decimal(previous_credit):
        raise HTTPException(409, 'Supplier credit exceeds the remaining original invoice value')
    from app.models.payment import Payment, PaymentAllocation
    if db.query(PaymentAllocation).join(Payment).filter(PaymentAllocation.supplier_invoice_id == invoice.id, Payment.status == 'APPROVED').first() or db.query(SupplierAdjustment).filter(SupplierAdjustment.supplier_invoice_id == invoice.id, SupplierAdjustment.status == 'DRAFT').first():
        raise HTTPException(409, 'Complete or void pending invoice payments/adjustments before settling the return credit')
    linked_ids = [line.goods_receipt_item_id for line in invoice.lines if line.goods_receipt_item_id]
    if len(linked_ids) != len(set(linked_ids)):
        raise HTTPException(409, 'Source invoice contains duplicate Receiving line links; reconcile them before return credit')
    source_invoice_lines = {line.goods_receipt_item_id: line for line in invoice.lines if line.goods_receipt_item_id}
    max_net = max_tax = ZERO
    for line in row.items:
        invoice_line = source_invoice_lines.get(line.goods_receipt_item_id)
        if not invoice_line or Decimal(invoice_line.quantity or 0) <= ZERO:
            raise HTTPException(409, 'Invoice lines must link uniquely to the returned Receiving lines')
        max_net += Decimal(invoice_line.line_amount) * line.quantity / Decimal(invoice_line.quantity)
        max_tax += Decimal(invoice_line.tax_amount or 0) * line.quantity / Decimal(invoice_line.quantity)
    previous_tax = db.query(func.coalesce(func.sum(InventoryReturn.credit_tax), 0)).filter(
        InventoryReturn.status == 'POSTED', InventoryReturn.supplier_invoice_id == invoice.id, InventoryReturn.credit_journal_id.is_not(None)).scalar()
    if net > money(max_net) or tax > min(money(max_tax), Decimal(invoice.tax_amount or 0) - Decimal(previous_tax)):
        raise HTTPException(409, 'Credit base/tax exceeds the source invoice evidence')
    clearing = account(db, row.clearing_account_id)
    payable = DirectCoaService(db).payable_account(invoice.supplier, source.location_id)
    balance = max(ZERO, Decimal(invoice.total_amount) - Decimal(invoice.paid_amount or 0) - Decimal(invoice.adjustment_amount or 0))
    applied = min(balance, gross)
    excess = gross - applied
    entries = [(payable.id, applied, ZERO), (clearing.id, ZERO, row.total_cost)]
    if excess:
        credit_account = account(db, data.supplier_credit_account_id)
        if credit_account.id in {clearing.id, payable.id} or credit_account.id in {line.inventory_account_id for line in row.items}:
            raise HTTPException(422, 'Choose a distinct supplier credit asset account')
        entries.append((credit_account.id, excess, ZERO))
        row.supplier_credit_account_id = credit_account.id
    if tax:
        vat = DirectCoaService(db).input_vat_account()
        if vat.id == clearing.id:
            raise HTTPException(422, 'Tax and return clearing accounts must differ')
        entries.append((vat.id, ZERO, tax))
    variance = net - Decimal(row.total_cost)
    if variance:
        variance_account = account(db, data.variance_account_id, 'EXPENSE')
        entries.append((variance_account.id, max(-variance, ZERO), max(variance, ZERO)))
    entry = journal(db, row, source, user, data.credit_date, 'SUPPLIER_RETURN_CREDIT', row.id, row.number, entries)
    row.supplier_invoice_id, row.credit_journal_id = invoice.id, entry.id
    row.credit_date, row.credit_reference = data.credit_date, data.credit_reference.strip()
    row.credit_net, row.credit_tax, row.credit_applied, row.supplier_credit = net, tax, applied, excess
    if applied:
        adjustment = SupplierAdjustment(adjustment_number=next_document_number(db, 'SCN'), adjustment_type='CREDIT_NOTE',
            supplier_invoice_id=invoice.id, supplier_id=invoice.supplier_id, adjustment_date=data.credit_date,
            amount=applied, adjustment_account_id=clearing.id, reason=f'Return {row.number}', notes=row.credit_reference,
            status='POSTED', business_unit_id=source.business_unit_id, location_id=source.location_id,
            department_id=source.department_id, journal_entry_id=entry.id, created_by_id=user.id,
            posted_by_id=user.id, posted_at=datetime.now(timezone.utc))
        db.add(adjustment)
        db.flush()
        row.supplier_adjustment_id = adjustment.id
        invoice.adjustment_amount = Decimal(invoice.adjustment_amount or 0) + applied
        from app.services.accounting_unpost import _sync_invoice_payable
        _sync_invoice_payable(db, invoice)
    audit(db, row, user, 'SETTLE_CREDIT', {'reference': row.credit_reference, 'gross': str(gross),
        'ap_applied': str(applied), 'supplier_credit': str(excess), 'explicit_variance': str(variance),
        'variance_account_id': data.variance_account_id})
    return row


def serialize(db, row):
    from app.services.inventory_return_completion import events, remaining_credit
    history = events(db, row)
    undone = {e.reverses_event_id for e in history if e.reverses_event_id}
    replacements = db.query(InventoryReplacement).filter(InventoryReplacement.return_item_id.in_([line.id for line in row.items])).all()
    replaced = {}
    for link in replacements:
        replaced[link.return_item_id] = replaced.get(link.return_item_id, ZERO) + link.quantity
    replacement_receipt_ids = {link.receipt_item.goods_receipt_id for link in replacements}
    replacement_credit = db.query(func.coalesce(func.sum(JournalLine.credit), 0)).join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id).filter(JournalEntry.reference_type == 'SUPPLIER_REPLACEMENT', JournalEntry.reference_id.in_(replacement_receipt_ids), JournalLine.account_id == row.clearing_account_id).scalar() if replacement_receipt_ids else ZERO
    return {'id': row.id, 'number': row.number, 'goods_receipt_id': row.goods_receipt_id,
        'receipt_number': row.receipt.receipt_number, 'supplier_id': row.receipt.supplier_id,
        'supplier_name': row.receipt.supplier.name if row.receipt.supplier else None,
        'warehouse_id': row.receipt.warehouse_id, 'return_date': row.return_date, 'purpose': row.purpose,
        'reason': row.reason, 'status': row.status, 'clearing_account_id': row.clearing_account_id,
        'total_cost': row.total_cost, 'journal_entry_id': row.journal_entry_id,
        'clearing_balance': ZERO if row.status == 'VOID' or row.credit_journal_id else Decimal(row.total_cost or 0) - Decimal(replacement_credit),
        'credit_journal_id': row.credit_journal_id, 'credit_reference': row.credit_reference,
        'supplier_invoice_id': row.supplier_invoice_id, 'credit_net': row.credit_net, 'credit_tax': row.credit_tax,
        'credit_applied': row.credit_applied, 'supplier_credit': row.supplier_credit,
        'supplier_credit_account_id': row.supplier_credit_account_id,
        'remaining_supplier_credit': remaining_credit(db, row),
        'events': [{'id': e.id, 'kind': e.kind, 'date': e.event_date, 'amount': e.amount,
                    'reference': e.reference, 'reason': e.reason, 'supplier_invoice_id': e.supplier_invoice_id,
                    'cash_account_id': e.cash_account_id, 'journal_entry_id': e.journal_entry_id,
                    'reverses_event_id': e.reverses_event_id, 'reversed': e.id in undone} for e in history],
        'items': [{'id': line.id, 'goods_receipt_item_id': line.goods_receipt_item_id,
            'product_id': line.receipt_item.product_id, 'code': line.receipt_item.product.code,
            'name': line.receipt_item.product.name, 'uom': line.uom,
            'quantity': line.quantity, 'unit_cost': line.unit_cost, 'line_cost': line.line_cost,
            'replaced_quantity': replaced.get(line.id, ZERO)} for line in row.items],
        'replacement_receipts': list({link.receipt_item.goods_receipt_id: {
            'id': link.receipt_item.goods_receipt_id, 'number': link.receipt_item.goods_receipt.receipt_number}
            for link in replacements}.values())}
