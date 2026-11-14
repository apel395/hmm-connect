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


def test_correct_recorded_warehouse_keeps_physical_in_and_inventory_untouched(stock_db):
    context, receipt = sample(stock_db)
    db, original, user, products, inventory, *_ = context
    new_warehouse = Warehouse(code="WH-HIST-EDIT", name="Historical corrected warehouse",
                              location_id=original.location_id, is_active=True)
    db.add(new_warehouse)
    db.flush()
    original_movement = active_receipt_stock(db, receipt.id)[0]
    initial_count = db.query(StockMovement).count()
    initial_qty = Decimal(inventory[0].quantity)
    initial_average = Decimal(inventory[0].average_cost)
    correct_historical_receiving(db, receipt.id, user,
        HistoricalReceiptCorrection(reason="Warehouse was entered incorrectly",
                                    warehouse_id=new_warehouse.id))
    db.refresh(original_movement)
    new_balance = db.query(Inventory).filter_by(warehouse_id=new_warehouse.id,
                                                product_id=products[0].id).first()
    assert receipt.warehouse_id == new_warehouse.id
    assert original_movement.warehouse_id == original.id
    assert original_movement.id == active_receipt_stock(db, receipt.id)[0].id
    assert Decimal(inventory[0].quantity) == initial_qty
    assert Decimal(inventory[0].average_cost) == initial_average
    assert not new_balance or Decimal(new_balance.quantity) == 0
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


def test_location_and_recorded_warehouse_correct_without_physical_stock_reassignment(stock_db):
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
    assert movement.location_id == new_location.id  # Metadata corrected in place.
    assert movement.warehouse_id == warehouse.id  # Physical source preserved.
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
    # Persist the genuine stock OUT first. The correction's rollback must not
    # roll back the unrelated operational movement used by this regression.
    db.commit()
    return location, out


def test_reporting_location_changes_original_source_metadata_without_stock_activity(stock_db):
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
    assert original.location_id == location.id  # Original IN corrected in place.
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


def test_recorded_warehouse_change_after_real_stock_usage_keeps_physical_activity(stock_db):
    context, receipt = sample(stock_db)
    db, warehouse, user, products, inventory, *_ = context
    original = active_receipt_stock(db, receipt.id)[0]
    location, actual_out = _real_consumption_and_corrected_location(
        db, warehouse, user, products[0], inventory[0])
    second = Warehouse(code="WH-HIST-CONSUMED", name="Corrected recorded warehouse",
                       location_id=location.id, is_active=True)
    db.add(second)
    db.flush()
    source_id = original.id
    before_qty = Decimal(inventory[0].quantity)
    before_avg = Decimal(inventory[0].average_cost)
    before_movement_count = db.query(StockMovement.id).count()
    corrected = correct_historical_receiving(db, receipt.id, user,
        HistoricalReceiptCorrection(reason="Correct recorded warehouse without stock movement",
                                    location_id=location.id, warehouse_id=second.id))
    db.refresh(original)
    db.refresh(actual_out)
    assert corrected.location_id == location.id
    assert corrected.warehouse_id == second.id
    assert original.warehouse_id == warehouse.id
    assert original.location_id == location.id
    assert original.id == source_id
    assert actual_out.location_id == warehouse.location_id
    assert actual_out.warehouse_id == warehouse.id
    assert Decimal(inventory[0].quantity) == before_qty
    assert Decimal(inventory[0].average_cost) == before_avg
    assert db.query(StockMovement.id).count() == before_movement_count
    assert db.query(StockMovement.id).filter(
        StockMovement.reference_type.in_(("GOODS_RECEIPT_UNPOST", "GOODS_RECEIPT_RETURN"))
    ).count() == 0


def _new_location_without_stock_activity(db, user):
    location = Location(code="LOC-HIST-REPORT-RETURN", name="Historical corrected report location",
                        location_type="HOTEL", is_active=True,
                        business_unit_id=user.default_business_unit_id)
    db.add(location)
    db.flush()
    db.add(LocationDepartment(location_id=location.id, department_id=user.default_department_id))
    db.commit()
    return location


def test_return_after_reporting_correction_uses_original_physical_stock_dimensions(stock_db):
    from app.services.goods_receipt_service import GoodsReceiptService
    context, receipt = sample(stock_db)
    db, warehouse, user, _, _, *_ = context
    old_source = active_receipt_stock(db, receipt.id)[0]
    original_location_id = old_source.location_id
    original_bu_id = old_source.business_unit_id
    original_department_id = old_source.department_id
    location = _new_location_without_stock_activity(db, user)
    correct_historical_receiving(db, receipt.id, user,
        HistoricalReceiptCorrection(reason="Correct reporting location before return",
                                    location_id=location.id, warehouse_id=warehouse.id))
    GoodsReceiptService.return_receipt(db, receipt_id=receipt.id, user=user)
    returned = db.query(StockMovement).filter_by(
        goods_receipt_id=receipt.id, reference_type="GOODS_RECEIPT_RETURN").one()
    assert returned.warehouse_id == warehouse.id
    assert returned.location_id == original_location_id
    assert returned.business_unit_id == original_bu_id
    assert returned.department_id == original_department_id
    assert receipt.location_id == location.id


def test_depost_after_reporting_correction_uses_original_physical_stock_dimensions(stock_db):
    from app.services.receiving_depost import depost_receiving
    context, receipt = sample(stock_db)
    db, warehouse, user, _, _, *_ = context
    original = active_receipt_stock(db, receipt.id)[0]
    original_location_id = original.location_id
    location = _new_location_without_stock_activity(db, user)
    correct_historical_receiving(db, receipt.id, user,
        HistoricalReceiptCorrection(reason="Correct reporting location before depost",
                                    location_id=location.id, warehouse_id=warehouse.id))
    depost_receiving(db, receipt.id, user, "Reopen corrected historical Receiving")
    reversed_row = db.query(StockMovement).filter_by(
        goods_receipt_id=receipt.id, reference_type="GOODS_RECEIPT_UNPOST").one()
    assert reversed_row.warehouse_id == warehouse.id
    assert reversed_row.location_id == original_location_id
    assert reversed_row.business_unit_id == original.business_unit_id
    assert reversed_row.department_id == original.department_id
    assert receipt.status == "DRAFT"


def test_location_only_corrects_legacy_header_warehouse_mismatch_without_stock_mutation(stock_db):
    """Production GRs may have a header warehouse unlike their source IN.

    Resubmitting all unchanged line values alongside a location correction
    must not turn that discrepancy into a physical warehouse transfer.
    """
    context, receipt = sample(stock_db)
    db, warehouse, user, products, inventory, *_ = context
    source = active_receipt_stock(db, receipt.id)[0]
    mismatch = Warehouse(code="WH-HIST-HEADER-ONLY", name="Legacy header selection",
                         location_id=warehouse.location_id, is_active=True)
    db.add(mismatch)
    db.flush()
    receipt.warehouse_id = mismatch.id
    db.commit()
    location, subsequent_out = _real_consumption_and_corrected_location(
        db, warehouse, user, products[0], inventory[0])
    before_qty = Decimal(inventory[0].quantity)
    before_avg = Decimal(inventory[0].average_cost)
    before_count = db.query(StockMovement).count()
    before_source = (source.id, source.warehouse_id,
                     Decimal(source.quantity), Decimal(source.unit_cost),
                     source.department_id, source.inventory_account_id)
    before_out_id = subsequent_out.id

    result = correct_historical_receiving(db, receipt.id, user,
        HistoricalReceiptCorrection(
            reason="Correct old reporting location without changing physical stock",
            location_id=location.id, warehouse_id=mismatch.id,
            items=[dict(
                item_id=receipt.items[0].id, quantity=Decimal("2"), unit_cost=Decimal("10"),
                destination_type="WAREHOUSE", destination_override_reason=None,
                expense_account_id=None, is_taxable=False, tax_rate=0,
            )],
        ))
    assert result.location_id == location.id
    assert result.warehouse_id == mismatch.id
    db.refresh(source)
    assert source.location_id == location.id  # Metadata replacement, not movement.
    assert (source.id, source.warehouse_id,
            Decimal(source.quantity), Decimal(source.unit_cost),
            source.department_id, source.inventory_account_id) == before_source
    assert db.query(StockMovement).count() == before_count
    assert db.get(StockMovement, before_out_id).warehouse_id == warehouse.id
    assert Decimal(inventory[0].quantity) == before_qty
    assert Decimal(inventory[0].average_cost) == before_avg
    invoice = db.query(SupplierInvoice).filter_by(goods_receipt_id=receipt.id).one()
    assert invoice.location_id == location.id


def test_location_with_real_quantity_edit_still_blocks_consumed_legacy_source(stock_db):
    context, receipt = sample(stock_db)
    db, warehouse, user, products, inventory, *_ = context
    mismatch = Warehouse(code="WH-HIST-QTY-MISMATCH", name="Legacy header mismatch",
                         location_id=warehouse.location_id, is_active=True)
    db.add(mismatch)
    db.flush()
    receipt.warehouse_id = mismatch.id
    db.commit()
    location, real_out = _real_consumption_and_corrected_location(
        db, warehouse, user, products[0], inventory[0])
    before_qty = Decimal(inventory[0].quantity)
    with pytest.raises(HTTPException, match="subsequent actual stock usage"):
        correct_historical_receiving(db, receipt.id, user,
            HistoricalReceiptCorrection(
                reason="Quantity correction after physical stock consumption",
                location_id=location.id, warehouse_id=mismatch.id,
                items=[dict(item_id=receipt.items[0].id, quantity=3)],
            ))
    db.refresh(receipt)
    assert receipt.location_id == warehouse.location_id
    assert receipt.warehouse_id == mismatch.id
    assert Decimal(inventory[0].quantity) == before_qty
    assert db.get(StockMovement, real_out.id).reference_type == "STORE_REQUEST"
