"""Full historical edits must never rewrite unrelated stock activity."""
from decimal import Decimal

from app.models.inventory import Inventory
from app.models.stock_movement import StockMovement
from app.models.supplier_invoice import SupplierInvoice
from app.models.warehouse import Warehouse
from app.schemas.goods_receipt import HistoricalReceiptCorrection
from app.services.receiving_historical_correction import correct_historical_receiving
from app.services.receiving_stock_cycle import active_receipt_stock
from test_receiving_historical_correction_1110 import sample
from test_stock_opname_functional import stock_db


def test_header_only_and_tax_correction_preserves_source_in(stock_db):
    context, receipt = sample(stock_db)
    db, _, user, _, _, *_ = context
    source = active_receipt_stock(db, receipt.id)[0]
    initial_count = db.query(StockMovement).count()
    item = receipt.items[0]
    corrected = correct_historical_receiving(db, receipt.id, user,
        HistoricalReceiptCorrection(
            reason="Correct historical entry classification",
            external_reference="DOC-HIST-123", notes="Rechecked against old delivery report",
            items=[dict(item_id=item.id, is_taxable=True, tax_rate=11)],
        ))
    invoice = db.query(SupplierInvoice).filter_by(goods_receipt_id=receipt.id).one()
    assert corrected.external_reference == "DOC-HIST-123"
    assert corrected.notes == "Rechecked against old delivery report"
    assert item.is_taxable and Decimal(item.tax_rate) == Decimal("11")
    assert invoice.lines[0].is_taxable and Decimal(invoice.lines[0].tax_rate) == Decimal("11")
    assert Decimal(invoice.total_amount) == Decimal("22.20")
    assert db.query(StockMovement).count() == initial_count
    assert active_receipt_stock(db, receipt.id)[0].id == source.id


def test_retarget_warehouse_relabels_original_in_without_stock_out(stock_db):
    context, receipt = sample(stock_db)
    db, original, user, products, inventory, *_ = context
    new_warehouse = Warehouse(code="WH-HIST-EDIT", name="Historical corrected warehouse",
                              location_id=original.location_id, is_active=True)
    db.add(new_warehouse)
    db.flush()
    original_movement = active_receipt_stock(db, receipt.id)[0]
    initial_count = db.query(StockMovement).count()
    initial_qty = Decimal(inventory[0].quantity)
    correct_historical_receiving(db, receipt.id, user,
        HistoricalReceiptCorrection(reason="Warehouse was entered incorrectly",
                                    warehouse_id=new_warehouse.id))
    db.refresh(original_movement)
    new_balance = db.query(Inventory).filter_by(warehouse_id=new_warehouse.id,
                                                product_id=products[0].id).one()
    assert receipt.warehouse_id == new_warehouse.id
    assert original_movement.warehouse_id == new_warehouse.id
    assert original_movement.id == active_receipt_stock(db, receipt.id)[0].id
    assert Decimal(inventory[0].quantity) == initial_qty - Decimal("2")
    assert Decimal(new_balance.quantity) == Decimal("2")
    assert db.query(StockMovement).count() == initial_count


def test_correct_direct_use_destination_removes_only_source_in(stock_db):
    context, receipt = sample(stock_db)
    db, _, user, _, inventory, expense, *_ = context
    original = active_receipt_stock(db, receipt.id)[0]
    count = db.query(StockMovement).count()
    starting_qty = Decimal(inventory[0].quantity)
    correct_historical_receiving(db, receipt.id, user,
        HistoricalReceiptCorrection(reason="Never entered warehouse, used directly",
            items=[dict(item_id=receipt.items[0].id, destination_type="DIRECT_USE",
                        destination_override_reason="Historical source was wrong",
                        expense_account_id=expense.id)]))
    assert receipt.destination_type == "DIRECT_USE"
    assert receipt.items[0].expense_account_id == expense.id
    assert active_receipt_stock(db, receipt.id) == []
    assert db.query(StockMovement).count() == count - 1
    assert Decimal(inventory[0].quantity) == starting_qty - Decimal("2")
    assert db.get(StockMovement, original.id) is None
