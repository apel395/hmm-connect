"""Atomic credit usage and compensating return reversal; original journals stay intact."""
from datetime import datetime, time, timezone
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import DBAPIError

from app.models.goods_receipt import GoodsReceipt, GoodsReceiptItem
from app.models.inventory import Inventory
from app.models.inventory_return import InventoryReturnEvent, InventoryReplacement
from app.models.journal_entry import JournalEntry
from app.models.payment import Payment, PaymentAllocation
from app.models.stock_movement import StockMovement
from app.models.supplier_adjustment import SupplierAdjustment
from app.models.supplier_invoice import SupplierInvoice, SupplierInvoiceLine
from app.services.accounting_unpost import _sync_invoice_payable
from app.services.direct_coa_service import DirectCoaService
from app.services.document_accounting import invoice_is_accounted
from app.services.document_number import next_document_number
from app.services.fiscal_period_service import FiscalPeriodService
from app.services.inventory_return_service import get_return, journal, audit, money, ZERO


def events(db, row):
    return db.query(InventoryReturnEvent).filter_by(return_id=row.id).order_by(InventoryReturnEvent.id).all()


def remaining_credit(db, row):
    used = db.query(func.coalesce(func.sum(InventoryReturnEvent.amount), 0)).filter(
        InventoryReturnEvent.return_id == row.id, InventoryReturnEvent.kind.in_(['APPLY', 'REFUND'])).scalar()
    restored = db.query(func.coalesce(func.sum(InventoryReturnEvent.amount), 0)).filter(
        InventoryReturnEvent.return_id == row.id, InventoryReturnEvent.kind == 'REVERSE_USE').scalar()
    return ZERO if row.status != 'POSTED' else Decimal(row.supplier_credit or 0) - Decimal(used) + Decimal(restored)


def lock_invoice(db, invoice_id):
    try:
        value = db.query(SupplierInvoice).filter_by(id=invoice_id).with_for_update(nowait=True).first()
    except DBAPIError as error:
        if getattr(error.orig, 'pgcode', None) == '55P03' or getattr(error.orig, 'sqlstate', None) == '55P03':
            raise HTTPException(409, 'Invoice is being processed; retry after Finance/payment completes') from error
        raise
    if not value or not invoice_is_accounted(db, value):
        raise HTTPException(409, 'Select an accounted supplier invoice')
    if db.query(PaymentAllocation).join(Payment).filter(PaymentAllocation.supplier_invoice_id == value.id,
            Payment.status == 'APPROVED').first() or db.query(SupplierAdjustment).filter(
                SupplierAdjustment.supplier_invoice_id == value.id, SupplierAdjustment.status == 'DRAFT').first():
        raise HTTPException(409, 'Complete or void pending invoice payments/adjustments first')
    return value


def validate_event(db, row, data, earliest):
    FiscalPeriodService.validate_posting_date(db, data.event_date)
    if data.event_date < earliest or not data.reference.strip() or not data.reason.strip():
        raise HTTPException(422, 'Enter a reference, reason and date on or after the source event')
    existing = db.query(InventoryReturnEvent).filter_by(request_key=str(data.request_key)).first()
    if existing and existing.return_id != row.id:
        raise HTTPException(409, 'Request key belongs to another return')
    return existing


def same_event(existing, data, kind, amount=None, reverses=None):
    same = (existing.kind == kind and existing.event_date == data.event_date
        and existing.reference == data.reference.strip() and existing.reason == data.reason.strip()
        and existing.reverses_event_id == reverses)
    if amount is not None:
        same = same and existing.amount == amount and existing.supplier_invoice_id == data.supplier_invoice_id and existing.cash_account_id == data.cash_account_id
    if not same:
        raise HTTPException(409, 'Request key was already used with different values')


def new_event(db, row, data, user, kind, amount, **kwargs):
    event = InventoryReturnEvent(return_id=row.id, request_key=str(data.request_key), kind=kind,
        event_date=data.event_date, reference=data.reference.strip(), reason=data.reason.strip(),
        amount=amount, created_by_id=user.id, **kwargs)
    db.add(event)
    db.flush()
    return event


def reverse_entries(db, journal_ids):
    entries = []
    for entry_id in journal_ids:
        entry = db.query(JournalEntry).filter_by(id=entry_id).with_for_update().first()
        if not entry or entry.status != 'POSTED':
            raise HTTPException(409, 'Source journal is no longer posted; reconcile source accounting first')
        entries.extend((line.account_id, Decimal(line.credit or 0), Decimal(line.debit or 0)) for line in entry.lines)
    return entries


def apply_credit(db, document_id, data, user):
    row, source = get_return(db, document_id, user)
    existing = validate_event(db, row, data, row.credit_date or row.return_date)
    if existing:
        same_event(existing, data, data.kind, money(data.amount))
        return row
    if row.status != 'POSTED' or not row.credit_journal_id or not row.supplier_credit_account_id:
        raise HTTPException(409, 'Select a posted return with a supplier credit balance')
    amount = money(data.amount)
    if amount > remaining_credit(db, row):
        raise HTTPException(409, 'Amount exceeds remaining supplier credit')
    # The credit's account is a historical snapshot; new uses require an active mapping.
    asset = DirectCoaService(db).account(row.supplier_credit_account_id, 'Supplier credit asset')
    invoice = None
    if data.kind == 'APPLY':
        if not data.supplier_invoice_id or data.cash_account_id:
            raise HTTPException(422, 'Select a target invoice only')
        invoice = lock_invoice(db, data.supplier_invoice_id)
        if (invoice.supplier_id != source.supplier_id or invoice.location_id != source.location_id
            or invoice.business_unit_id != source.business_unit_id or invoice.currency != 'IDR'):
            raise HTTPException(409, 'Target invoice must have the same supplier, location, business unit and IDR currency')
        if data.event_date < invoice.invoice_date:
            raise HTTPException(422, 'Credit use date cannot precede the target invoice')
        balance = max(ZERO, Decimal(invoice.total_amount) - Decimal(invoice.paid_amount or 0) - Decimal(invoice.adjustment_amount or 0))
        if amount > balance:
            raise HTTPException(409, 'Amount exceeds target invoice outstanding balance')
        debit = DirectCoaService(db).payable_account(invoice.supplier, source.location_id)
    else:
        if not data.cash_account_id or data.supplier_invoice_id:
            raise HTTPException(422, 'Select a cash/bank refund account only')
        debit = DirectCoaService(db).account(data.cash_account_id, 'Supplier refund bank/cash')
        if debit.account_type != 'ASSET' or debit.normal_balance != 'DEBIT' or debit.account_subtype not in DirectCoaService.BANK_SUBTYPES:
            raise HTTPException(422, 'Refund requires an active debit-balance cash/bank account')
    if debit.id == asset.id:
        raise HTTPException(422, 'Settlement and supplier-credit accounts must differ')
    event = new_event(db, row, data, user, data.kind, amount,
        supplier_invoice_id=data.supplier_invoice_id, cash_account_id=data.cash_account_id)
    entry = journal(db, row, source, user, data.event_date, 'SUPPLIER_CREDIT_USE', event.id,
        event.reference, [(debit.id, amount, ZERO), (asset.id, ZERO, amount)])
    event.journal_entry_id = entry.id
    if invoice:
        adjustment = SupplierAdjustment(adjustment_number=next_document_number(db, 'SCN'), adjustment_type='CREDIT_NOTE',
            supplier_invoice_id=invoice.id, supplier_id=source.supplier_id, adjustment_date=data.event_date,
            amount=amount, adjustment_account_id=asset.id, reason=data.reason.strip(), notes=f'{row.number} / {event.reference}',
            status='POSTED', business_unit_id=source.business_unit_id, location_id=source.location_id,
            department_id=source.department_id, journal_entry_id=entry.id, created_by_id=user.id,
            posted_by_id=user.id, posted_at=datetime.now(timezone.utc))
        db.add(adjustment); db.flush()
        event.supplier_adjustment_id = adjustment.id
        invoice.adjustment_amount = Decimal(invoice.adjustment_amount or 0) + amount
        _sync_invoice_payable(db, invoice)
    audit(db, row, user, data.kind, {'event_id': event.id, 'amount': str(amount), 'reference': event.reference,
        'target_invoice_id': data.supplier_invoice_id, 'cash_account_id': data.cash_account_id})
    return row


def undo_adjustment(db, invoice, adjustment_id, amount):
    adjustment = db.query(SupplierAdjustment).filter_by(id=adjustment_id).with_for_update().first()
    if not adjustment or adjustment.status != 'POSTED' or Decimal(invoice.adjustment_amount or 0) < amount:
        raise HTTPException(409, 'Source invoice adjustment changed; reconcile it before reversal')
    adjustment.status = 'VOID'
    invoice.adjustment_amount = Decimal(invoice.adjustment_amount or 0) - amount
    _sync_invoice_payable(db, invoice)


def reverse_use(db, document_id, event_id, data, user):
    row, source = get_return(db, document_id, user)
    original = db.query(InventoryReturnEvent).filter_by(id=event_id, return_id=row.id).first()
    if not original or original.kind not in ('APPLY', 'REFUND'):
        raise HTTPException(404, 'Supplier credit use/refund not found')
    existing = validate_event(db, row, data, original.event_date)
    if existing:
        same_event(existing, data, 'REVERSE_USE', reverses=original.id)
        return row
    if row.status != 'POSTED' or db.query(InventoryReturnEvent).filter_by(reverses_event_id=original.id).first():
        raise HTTPException(409, 'Credit use/refund has already been reversed')
    invoice = lock_invoice(db, original.supplier_invoice_id) if original.supplier_invoice_id else None
    FiscalPeriodService.validate_posting_date(db, original.event_date)
    entries = reverse_entries(db, [original.journal_entry_id])
    event = new_event(db, row, data, user, 'REVERSE_USE', original.amount, reverses_event_id=original.id)
    entry = journal(db, row, source, user, data.event_date, 'SUPPLIER_CREDIT_USE_REVERSAL', event.id, event.reference, entries)
    event.journal_entry_id = entry.id
    if invoice:
        undo_adjustment(db, invoice, original.supplier_adjustment_id, original.amount)
    audit(db, row, user, 'REVERSE_CREDIT_USE', {'event_id': event.id, 'reverses_event_id': original.id,
        'reason': event.reason, 'reference': event.reference})
    return row


def reverse_return(db, document_id, data, user):
    row, source = get_return(db, document_id, user)
    existing = validate_event(db, row, data, row.credit_date or row.return_date)
    if existing:
        same_event(existing, data, 'REVERSE_RETURN')
        return row
    if row.status != 'POSTED':
        raise HTTPException(409, 'Only a posted return can be reversed')
    history = events(db, row)
    undone = {event.reverses_event_id for event in history if event.kind == 'REVERSE_USE'}
    if any(event.kind in ('APPLY', 'REFUND') and event.id not in undone for event in history):
        raise HTTPException(409, 'Reverse supplier credit uses/refunds before reversing this return')
    # Source periods stay locked even when a later accounting period is open.
    source_journal = db.get(JournalEntry, row.journal_entry_id)
    FiscalPeriodService.validate_posting_date(db, source_journal.posting_date)
    links = db.query(InventoryReplacement).filter(InventoryReplacement.return_item_id.in_([line.id for line in row.items])).all()
    replacement_ids = sorted({link.receipt_item.goods_receipt_id for link in links})
    replacement_journals = []
    for replacement_id in replacement_ids:
        replacement = db.query(GoodsReceipt).filter_by(id=replacement_id).with_for_update().one()
        if replacement.status != 'POSTED' or data.event_date < replacement.received_at.date():
            raise HTTPException(409, 'Replacement is not posted or reversal date precedes replacement')
        if db.query(SupplierInvoice).filter(SupplierInvoice.goods_receipt_id == replacement_id,
                SupplierInvoice.status.notin_(['VOID', 'REJECTED'])).first() or db.query(SupplierInvoiceLine).join(SupplierInvoice, SupplierInvoice.id == SupplierInvoiceLine.supplier_invoice_id).join(GoodsReceiptItem, GoodsReceiptItem.id == SupplierInvoiceLine.goods_receipt_item_id).filter(GoodsReceiptItem.goods_receipt_id == replacement_id, SupplierInvoice.status.notin_(['VOID', 'REJECTED'])).first():
            raise HTTPException(409, 'Replacement has an invoice dependency; reconcile it before reversal')
        entry = db.query(JournalEntry).filter_by(reference_type='SUPPLIER_REPLACEMENT', reference_id=replacement_id).one()
        FiscalPeriodService.validate_posting_date(db, entry.posting_date)
        replacement_journals.append(entry.id)
    if row.credit_journal_id:
        FiscalPeriodService.validate_posting_date(db, db.get(JournalEntry, row.credit_journal_id).posting_date)
    invoice = lock_invoice(db, row.supplier_invoice_id) if row.credit_journal_id else None
    journal_ids = [row.journal_entry_id, *replacement_journals] + ([row.credit_journal_id] if row.credit_journal_id else [])
    entries = reverse_entries(db, journal_ids)
    # Reverse the physical net of the return and all linked replacements. Exact
    # monetary snapshots are copied with opposite signs; never rewrite old movements.
    movements = db.query(StockMovement).filter(
        ((StockMovement.reference_type == 'SUPPLIER_RETURN') & (StockMovement.reference_id == row.id)) |
        ((StockMovement.reference_type == 'SUPPLIER_REPLACEMENT') & StockMovement.reference_id.in_(replacement_ids))).order_by(StockMovement.id).all()
    original_moves = [m for m in movements if m.reference_type == 'SUPPLIER_RETURN']
    expected = {line.goods_receipt_item_id: line for line in row.items}
    if len(original_moves) != len(expected) or {m.goods_receipt_item_id for m in original_moves} != set(expected):
        raise HTTPException(409, 'Return movement history is incomplete; reconcile before reversal')
    for movement in original_moves:
        line = expected[movement.goods_receipt_item_id]
        if (movement.product_id != line.receipt_item.product_id or movement.warehouse_id != source.warehouse_id
            or Decimal(movement.quantity) != -Decimal(line.quantity) or movement.recorded_value != line.line_cost
            or movement.unit_cost != line.unit_cost or movement.inventory_account_id != line.inventory_account_id):
            raise HTTPException(409, 'Return stock snapshot changed; reconcile before reversal')
    replacement_moves = [m for m in movements if m.reference_type == 'SUPPLIER_REPLACEMENT']
    expected_replacements = {link.goods_receipt_item_id: link for link in links}
    if len(replacement_moves) != len(expected_replacements) or {m.goods_receipt_item_id for m in replacement_moves} != set(expected_replacements):
        raise HTTPException(409, 'Replacement movement history is incomplete; reconcile before reversal')
    for movement in replacement_moves:
        link = expected_replacements[movement.goods_receipt_item_id]
        if (movement.warehouse_id != source.warehouse_id or movement.product_id != link.receipt_item.product_id
            or movement.quantity != link.quantity or movement.recorded_value != link.receipt_item.replacement_line_value
            or movement.inventory_account_id != link.return_item.inventory_account_id or movement.unit_cost != link.return_item.unit_cost):
            raise HTTPException(409, 'Replacement stock snapshot changed; reconcile before reversal')
    prepared = {}
    for movement in movements:
        qty = -Decimal(movement.quantity)
        value = Decimal(movement.recorded_value) * (1 if qty > 0 else -1)
        key = movement.product_id
        values = prepared.setdefault(key, [ZERO, ZERO, ZERO, movement.inventory_account_id])
        values[0] += qty
        values[1] += qty * Decimal(movement.unit_cost)
        values[2] += value
    stocks = {}
    for product_id, (qty, raw_value, _, _) in sorted(prepared.items()):
        stock = db.query(Inventory).filter_by(product_id=product_id, warehouse_id=source.warehouse_id).with_for_update().first()
        if not stock or qty < 0:
            raise HTTPException(409, 'Inventory history is incomplete; reconcile before reversal')
        stocks[product_id] = stock
    event = new_event(db, row, data, user, 'REVERSE_RETURN', row.total_cost)
    entry = journal(db, row, source, user, data.event_date, 'SUPPLIER_RETURN_REVERSAL', event.id, event.reference, entries)
    event.journal_entry_id = entry.id
    for product_id, (qty, raw_value, value, coa) in prepared.items():
        stock = stocks[product_id]
        if qty:
            new_qty = Decimal(stock.quantity) + qty
            if new_qty <= 0:
                raise HTTPException(409, 'Stock cannot support reversal; reconcile source movements first')
            stock.average_cost = ((Decimal(stock.quantity) * Decimal(stock.average_cost or 0) + raw_value) / new_qty).quantize(Decimal('.0001'), rounding=ROUND_HALF_UP)
            stock.quantity = new_qty
        # Keep zero-net stock events out of the movement ledger.
        if qty or value:
            db.add(StockMovement(product_id=product_id, warehouse_id=source.warehouse_id,
                business_unit_id=source.business_unit_id, department_id=source.department_id, location_id=source.location_id,
                movement_type='IN', quantity=qty, unit_cost=(raw_value / qty if qty else ZERO), recorded_value=value,
                reference_type='SUPPLIER_RETURN_REVERSAL', reference_id=event.id, goods_receipt_id=source.id,
                inventory_account_id=coa, offset_account_id=row.clearing_account_id, journal_entry_id=entry.id,
                created_at=datetime.combine(data.event_date, time(), tzinfo=timezone.utc), notes=f'Reversal {row.number}: {event.reason}'))
    if invoice and row.supplier_adjustment_id:
        undo_adjustment(db, invoice, row.supplier_adjustment_id, Decimal(row.credit_applied))
    for replacement_id in replacement_ids:
        db.get(GoodsReceipt, replacement_id).status = 'VOID'
    row.status = 'VOID'
    audit(db, row, user, 'REVERSE_RETURN', {'event_id': event.id, 'reason': event.reason,
        'original_journal_ids': journal_ids, 'reversal_journal_id': entry.id})
    return row
