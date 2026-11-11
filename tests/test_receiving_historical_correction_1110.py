"""Administrator numeric correction is not a physical inventory movement."""
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.fiscal_period import FiscalPeriod
from app.models.journal_entry import JournalEntry
from app.models.role import Role
from app.models.stock_movement import StockMovement
from app.models.supplier_invoice import SupplierInvoice
from app.schemas.goods_receipt import HistoricalReceiptCorrection
from app.services.goods_receipt_service import GoodsReceiptService as Service
from app.services.receiving_depost import depost_receiving
from app.services.receiving_historical_correction import correct_historical_receiving
from app.services.receiving_stock_cycle import active_receipt_stock
from test_stock_opname_functional import stock_db
from test_receiving_line_destinations import setup_receiving, create


def sample(stock_db):
    context = setup_receiving(stock_db)
    db, warehouse, user, products, inventory, *_ = context
    receipt = create(context, items=[dict(product_id=products[0].id, quantity=2, unit_cost=10)])
    Service.post(db, receipt_id=receipt.id, user=user)
    receipt.source_type = 'HISTORICAL_ENTRY'
    db.commit()
    return context, receipt


def corrected(db, receipt, user, quantity=None, unit_cost=None):
    return correct_historical_receiving(db, receipt.id, user,
        HistoricalReceiptCorrection(reason='Fix historical data entry', items=[dict(
            item_id=receipt.items[0].id, quantity=quantity, unit_cost=unit_cost)]))


def test_admin_corrects_history_without_new_stock_movements(stock_db):
    data, receipt = sample(stock_db)
    db, _, user, products, inventory, *_ = data
    later = create(data, items=[dict(product_id=products[0].id, quantity=3, unit_cost=30)])
    Service.post(db, receipt_id=later.id, user=user)
    depost_receiving(db, later.id, user, 'Wrong historical receipt')
    old_movement = active_receipt_stock(db, receipt.id)[0]
    movement_count = db.query(StockMovement).count()
    before_qty = Decimal(inventory[0].quantity)
    before_value = before_qty * Decimal(inventory[0].average_cost)

    corrected(db, receipt, user, quantity=4, unit_cost=12)

    assert receipt.status == 'POSTED'
    assert len(active_receipt_stock(db, receipt.id)) == 1
    assert db.query(StockMovement).count() == movement_count
    assert old_movement.movement_type == 'IN' and old_movement.quantity == 4 and old_movement.unit_cost == 12
    assert inventory[0].quantity == before_qty + 2
    assert abs(inventory[0].quantity * inventory[0].average_cost - (before_value + 28)) < Decimal('0.01')
    invoice = db.query(SupplierInvoice).filter_by(goods_receipt_id=receipt.id, status='DRAFT').one()
    assert invoice.lines[0].quantity == 4 and invoice.lines[0].unit_price == 12
    assert invoice.total_amount == 48
    journal = db.query(JournalEntry).filter_by(reference_type='GOODS_RECEIPT', reference_id=receipt.id).one()
    assert sum(line.debit for line in journal.lines) == sum(line.credit for line in journal.lines) == 48


def test_other_valid_receipt_depost_is_not_downstream_consumption(stock_db):
    data, first = sample(stock_db)
    db, _, user, products, inventory, *_ = data
    second = create(data, items=[dict(product_id=products[0].id, quantity=3, unit_cost=20)])
    Service.post(db, receipt_id=second.id, user=user)
    depost_receiving(db, second.id, user, 'Second receipt entered incorrectly')
    # Its reversal is an OUT in the ledger, but is not physical consumption.
    depost_receiving(db, first.id, user, 'Correct first receiving location')
    assert first.status == 'DRAFT' and second.status == 'DRAFT'
    assert inventory[0].quantity == 20


def test_repeated_historical_correction_keeps_one_receipt_movement(stock_db):
    data, receipt = sample(stock_db)
    db, _, user, _, inventory, *_ = data
    count = db.query(StockMovement).count()
    corrected(db, receipt, user, quantity=4)
    corrected(db, receipt, user, unit_cost=15)
    assert db.query(StockMovement).count() == count
    assert active_receipt_stock(db, receipt.id)[0].quantity == 4
    assert active_receipt_stock(db, receipt.id)[0].unit_cost == 15
    assert inventory[0].quantity == 24
    invoice = db.query(SupplierInvoice).filter_by(goods_receipt_id=receipt.id).one()
    assert invoice.lines[0].quantity == 4 and invoice.lines[0].unit_price == 15


def test_admin_adds_historical_stock_line_with_only_its_new_source_in(stock_db):
    data, receipt = sample(stock_db)
    db, _, user, products, inventory, *_ = data
    old_movement = active_receipt_stock(db, receipt.id)[0]
    starting_qty = Decimal(inventory[0].quantity)
    result = correct_historical_receiving(db, receipt.id, user,
        HistoricalReceiptCorrection(reason='Missing historical goods', add_items=[dict(
            product_id=products[0].id, quantity=3, unit_cost=14)]))

    assert len(result.items) == 2
    movements = active_receipt_stock(db, receipt.id)
    assert len(movements) == 2 and movements[0].id == old_movement.id
    assert movements[1].goods_receipt_item_id == result.items[1].id
    assert movements[1].quantity == 3 and movements[1].unit_cost == 14
    assert inventory[0].quantity == starting_qty + 3
    invoice = db.query(SupplierInvoice).filter_by(goods_receipt_id=receipt.id).one()
    assert {line.goods_receipt_item_id for line in invoice.lines} == {item.id for item in receipt.items}
    assert invoice.total_amount == receipt.total_amount == 62


def test_admin_removes_mistaken_historical_item_without_stock_out(stock_db):
    data, receipt = sample(stock_db)
    db, _, user, _, inventory, *_ = data
    added_receipt_item = receipt.items[0]
    added_movement = active_receipt_stock(db, receipt.id)[0]
    initial_movement_count = db.query(StockMovement).count()
    initial_qty = Decimal(inventory[0].quantity)
    correct_historical_receiving(db, receipt.id, user,
        HistoricalReceiptCorrection(reason='Item was never delivered',
            remove_item_ids=[added_receipt_item.id], add_items=[dict(
                product_id=added_receipt_item.product_id, quantity=1, unit_cost=20)]))

    assert added_movement not in active_receipt_stock(db, receipt.id)
    assert db.query(StockMovement).count() == initial_movement_count
    assert inventory[0].quantity == initial_qty - 1
    assert receipt.items[0].id != added_receipt_item.id
    assert receipt.total_amount == 20
    assert db.query(SupplierInvoice).filter_by(goods_receipt_id=receipt.id).one().lines[0].goods_receipt_item_id == receipt.items[0].id


def test_admin_removes_one_historical_line_without_reversal(stock_db):
    data, receipt = sample(stock_db)
    db, _, user, products, inventory, *_ = data
    second = correct_historical_receiving(db, receipt.id, user,
        HistoricalReceiptCorrection(reason='Add missing stock line', add_items=[dict(
            product_id=products[0].id, quantity=3, unit_cost=14)])).items[1]
    initial_qty = Decimal(inventory[0].quantity)
    movement_count = db.query(StockMovement).count()
    correct_historical_receiving(db, receipt.id, user,
        HistoricalReceiptCorrection(reason='Second line never existed', remove_item_ids=[second.id]))
    assert len(receipt.items) == 1
    assert db.query(StockMovement).count() == movement_count - 1
    assert inventory[0].quantity == initial_qty - 3
    assert receipt.total_amount == 20


def test_admin_adds_direct_use_item_without_stock_movement(stock_db):
    data, receipt = sample(stock_db)
    db, _, user, products, inventory, expense, *_ = data
    old_count = db.query(StockMovement).count()
    old_qty = Decimal(inventory[0].quantity)
    correct_historical_receiving(db, receipt.id, user,
        HistoricalReceiptCorrection(reason='Direct use purchase missing', add_items=[dict(
            product_id=products[1].id, quantity=2, unit_cost=18,
            expense_account_id=expense.id)]))
    assert len(receipt.items) == 2 and receipt.destination_type == 'MIXED'
    assert db.query(StockMovement).count() == old_count
    assert inventory[0].quantity == old_qty
    assert receipt.total_amount == 56
    invoice = db.query(SupplierInvoice).filter_by(goods_receipt_id=receipt.id).one()
    assert len(invoice.lines) == 2 and invoice.total_amount == 56


def test_historical_added_line_can_be_corrected_again(stock_db):
    data, receipt = sample(stock_db)
    db, _, user, products, inventory, *_ = data
    correct_historical_receiving(db, receipt.id, user,
        HistoricalReceiptCorrection(reason='Add missing goods', add_items=[dict(
            product_id=products[0].id, quantity=3, unit_cost=14)]))
    added_line = receipt.items[1]
    count = db.query(StockMovement).count()
    correct_historical_receiving(db, receipt.id, user,
        HistoricalReceiptCorrection(reason='Fix source count', items=[dict(
            item_id=added_line.id, quantity=4)]))
    assert db.query(StockMovement).count() == count
    assert active_receipt_stock(db, receipt.id)[1].quantity == 4
    assert receipt.total_amount == 76
    invoice = db.query(SupplierInvoice).filter_by(goods_receipt_id=receipt.id).one()
    assert {line.goods_receipt_item_id: line.quantity for line in invoice.lines}[added_line.id] == 4


def test_admin_cannot_remove_last_historical_item_without_replacement(stock_db):
    data, receipt = sample(stock_db)
    db, _, user, _, inventory, *_ = data
    old_qty = Decimal(inventory[0].quantity)
    with pytest.raises(HTTPException, match='keep at least one'):
        correct_historical_receiving(db, receipt.id, user,
            HistoricalReceiptCorrection(reason='Bad entry', remove_item_ids=[receipt.items[0].id]))
    assert len(receipt.items) == 1 and inventory[0].quantity == old_qty


def test_historical_addition_cannot_overwrite_later_stock_usage(stock_db):
    data, receipt = sample(stock_db)
    db, warehouse, user, products, inventory, *_ = data
    db.add(StockMovement(product_id=products[0].id, warehouse_id=warehouse.id,
        movement_type='OUT', quantity=1, unit_cost=10,
        reference_type='STORE_REQUEST', reference_id=9))
    db.commit()
    old_count = db.query(StockMovement).count()
    with pytest.raises(HTTPException, match='actual stock usage'):
        correct_historical_receiving(db, receipt.id, user,
            HistoricalReceiptCorrection(reason='Missing old receipt line', add_items=[dict(
                product_id=products[0].id, quantity=1, unit_cost=10)]))
    assert len(receipt.items) == 1 and db.query(StockMovement).count() == old_count


def test_forged_depost_reversal_cannot_bypass_consumption_guard(stock_db):
    data, receipt = sample(stock_db)
    db, warehouse, user, products, inventory, *_ = data
    db.add(StockMovement(product_id=products[0].id, warehouse_id=warehouse.id,
        movement_type='OUT', quantity=2, unit_cost=10,
        reference_type='GOODS_RECEIPT_UNPOST', reference_id=999,
        notes='Depost reversal of stock movement 123456: fake'))
    db.commit()
    with pytest.raises(HTTPException, match='actual stock usage or adjustment'):
        corrected(db, receipt, user, quantity=3)
    assert receipt.items[0].quantity == 2


@pytest.mark.parametrize('problem', [
    'ordinary_user', 'live_receipt', 'real_stock_out', 'confirmed_invoice', 'closed_period', 'posted_journal',
])
def test_unsafe_historical_correction_has_no_partial_changes(stock_db, problem):
    data, receipt = sample(stock_db)
    db, warehouse, user, products, inventory, *_ = data
    invoice = db.query(SupplierInvoice).filter_by(goods_receipt_id=receipt.id).one()
    journal = db.query(JournalEntry).filter_by(reference_type='GOODS_RECEIPT', reference_id=receipt.id).one()
    if problem == 'ordinary_user':
        user.roles = [Role(name='STORE')]
    elif problem == 'live_receipt':
        receipt.source_type = 'LIVE'
    elif problem == 'real_stock_out':
        db.add(StockMovement(product_id=products[0].id, warehouse_id=warehouse.id,
            movement_type='OUT', quantity=1, unit_cost=10, reference_type='STORE_REQUEST', reference_id=1))
    elif problem == 'confirmed_invoice':
        invoice.supplier_invoice_number = 'REAL-SUPPLIER-NUMBER'
    elif problem == 'closed_period':
        period = db.query(FiscalPeriod).one()
        period.is_open = False
        period.is_closed = True
    elif problem == 'posted_journal':
        journal.status = 'POSTED'
    db.commit()
    original_qty = Decimal(inventory[0].quantity)
    original_movement = active_receipt_stock(db, receipt.id)[0]
    movement_count = db.query(StockMovement).count()
    with pytest.raises(HTTPException):
        corrected(db, receipt, user, quantity=4, unit_cost=12)
    assert inventory[0].quantity == original_qty
    assert receipt.items[0].quantity == original_movement.quantity == 2
    assert db.query(StockMovement).count() == movement_count
