"""Full historical edits must never rewrite unrelated stock activity."""
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.inventory import Inventory
from app.models.location import Location
from app.models.location_department import LocationDepartment
from app.models.supplier import Supplier
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


def test_supplier_correction_updates_only_the_linked_draft(stock_db):
    context, receipt = sample(stock_db)
    db, _, user, _, _, *_ = context
    new_supplier = Supplier(code="SUP-HIST-ALT", name="Correct historical supplier", is_active=True)
    db.add(new_supplier)
    db.flush()
    movement = active_receipt_stock(db, receipt.id)[0]
    count = db.query(StockMovement).count()
    correct_historical_receiving(db, receipt.id, user,
        HistoricalReceiptCorrection(reason="Historical supplier was incorrect",
                                     supplier_id=new_supplier.id))
    invoice = db.query(SupplierInvoice).filter_by(goods_receipt_id=receipt.id).one()
    assert receipt.supplier_id == invoice.supplier_id == new_supplier.id
    assert db.query(StockMovement).count() == count
    assert active_receipt_stock(db, receipt.id)[0].id == movement.id


def test_location_and_warehouse_correction_updates_only_original_source(stock_db):
    context, receipt = sample(stock_db)
    db, warehouse, user, products, inventory, *_ = context
    new_location = Location(code="LOC-HIST-EDIT", name="Correct receiving site",
                            location_type="HOTEL", is_active=True,
                            business_unit_id=user.default_business_unit_id)
    db.add(new_location)
    db.flush()
    db.add(LocationDepartment(location_id=new_location.id, department_id=user.default_department_id))
    new_warehouse = Warehouse(code="WH-HIST-NEWLOC", name="Corrected location warehouse",
                              location_id=new_location.id, is_active=True)
    db.add(new_warehouse)
    db.flush()
    movement = active_receipt_stock(db, receipt.id)[0]
    count = db.query(StockMovement).count()
    correct_historical_receiving(db, receipt.id, user,
        HistoricalReceiptCorrection(reason="Wrong receiving site on old entry",
            location_id=new_location.id, warehouse_id=new_warehouse.id))
    assert receipt.location_id == new_location.id
    assert movement.location_id == new_location.id
    assert movement.warehouse_id == new_warehouse.id
    assert db.query(StockMovement).count() == count
    invoice = db.query(SupplierInvoice).filter_by(goods_receipt_id=receipt.id).one()
    assert invoice.location_id == new_location.id


def _real_consumption_and_corrected_location(db, warehouse, user, product, inventory):
    location = Location(code="LOC-HIST-REPORT", name="Corrected historical reporting location",
                        location_type="HOTEL", is_active=True,
                        business_unit_id=user.default_business_unit_id)
    db.add(location)
    db.flush()
    db.add(LocationDepartment(location_id=location.id, department_id=user.default_department_id))
    out = StockMovement(
        product_id=product.id, warehouse_id=warehouse.id,
        business_unit_id=user.default_business_unit_id, location_id=warehouse.location_id,
        department_id=user.default_department_id, movement_type="OUT",
        quantity=Decimal("1"), unit_cost=Decimal("10"),
        reference_type="STORE_REQUEST", reference_id=9959)
    db.add(out)
    inventory.quantity -= Decimal("1")
    db.flush()
    return location, out


def test_reporting_location_change_preserves_consumed_stock_and_source_location(stock_db):
    context, receipt = sample(stock_db)
    db, warehouse, user, products, inventory, *_ = context
    original = active_receipt_stock(db, receipt.id)[0]
    location, actual_out = _real_consumption_and_corrected_location(
        db, warehouse, user, products[0], inventory[0])
    stock_qty = Decimal(inventory[0].quantity)
    stock_cost = Decimal(inventory[0].average_cost)
    initial_movement_count = db.query(StockMovement.id).count()
    original_location_id = original.location_id
    original_warehouse_id = original.warehouse_id

    # Warehouse ID is deliberately supplied unchanged, as in the full UI form.
    correct_historical_receiving(db, receipt.id, user,
        HistoricalReceiptCorrection(reason="Correct historical reporting location only",
                                    location_id=location.id, warehouse_id=warehouse.id))
    db.refresh(original)
    db.refresh(actual_out)
    assert receipt.location_id == location.id
    assert receipt.warehouse_id == original_warehouse_id
    assert original.location_id == original_location_id
    assert original.warehouse_id == original_warehouse_id
    assert actual_out.location_id == original_location_id
    assert actual_out.warehouse_id == original_warehouse_id
    assert db.query(StockMovement.id).count() == initial_movement_count
    assert Decimal(inventory[0].quantity) == stock_qty
    assert Decimal(inventory[0].average_cost) == stock_cost
    invoice = db.query(SupplierInvoice).filter_by(goods_receipt_id=receipt.id).one()
    assert invoice.location_id == location.id
    # Subsequent reporting edits must not try to reconcile/transfer old physical stock.
    correct_historical_receiving(db, receipt.id, user,
        HistoricalReceiptCorrection(reason="Fix historical narrative later",
                                    notes="Rechecked against supplier paperwork"))
    assert receipt.notes == "Rechecked against supplier paperwork"
    assert db.query(StockMovement.id).count() == initial_movement_count


def test_physical_warehouse_change_still_blocked_after_real_stock_usage(stock_db):
    context, receipt = sample(stock_db)
    db, warehouse, user, products, inventory, *_ = context
    original = active_receipt_stock(db, receipt.id)[0]
    location, actual_out = _real_consumption_and_corrected_location(
        db, warehouse, user, products[0], inventory[0])
    second = Warehouse(code="WH-HIST-CONSUMED", name="Corrected physical warehouse",
                       location_id=location.id, is_active=True)
    db.add(second)
    db.flush()
    source_id = original.id
    before_qty = Decimal(inventory[0].quantity)
    with pytest.raises(HTTPException, match="subsequent actual stock usage"):
        correct_historical_receiving(db, receipt.id, user,
            HistoricalReceiptCorrection(reason="Try to physically retarget used stock",
                                        location_id=location.id, warehouse_id=second.id))
    db.refresh(receipt)
    assert receipt.location_id == warehouse.location_id
    assert receipt.warehouse_id == warehouse.id
    assert db.get(StockMovement, source_id).warehouse_id == warehouse.id
    assert Decimal(inventory[0].quantity) == before_qty
    assert db.query(StockMovement.id).filter(StockMovement.reference_type == "STORE_REQUEST").count() == 1
