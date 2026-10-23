from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.accounting_setting import AccountingSetting
from app.models.chart_of_account import ChartOfAccount
from app.models.general_ledger import GeneralLedger
from app.models.journal_entry import JournalEntry
from app.models.role import Role
from app.models.stock_movement import StockMovement
from app.models.supplier import Supplier
from app.schemas.goods_receipt import GoodsReceiptCreate, GoodsReceiptUpdate, GoodsReceiptCostCorrection
from app.services.goods_receipt_service import GoodsReceiptService as Service
from app.services.receiving_destination import master_destination, line_destination, resolve_destination
from app.services.direct_coa_service import DirectCoaService
from test_stock_opname_functional import stock_db


def setup_receiving(stock_db):
    db, warehouse, user, products, inventory = stock_db
    user.roles = [Role(name="SYSTEM_ADMINISTRATOR")]
    expense = db.query(ChartOfAccount).filter_by(account_type="EXPENSE").one()
    for product, treatment in zip(products, ["STOCK", "DIRECT_USE"]):
        product.inventory_treatment = treatment
        product.purchase_account_id = expense.id
        product.catalog_type = "HOTEL"
    ap = ChartOfAccount(account_number="200-100-999", account_name="AP Suspense", account_type="LIABILITY", normal_balance="CREDIT", is_posting=True, is_active=True)
    supplier = Supplier(code="LINES-SUP", name="Supplier", is_active=True)
    db.add_all([ap, supplier]); db.flush()
    db.add(AccountingSetting(setting_key="AP_SUSPENSE_ACCOUNT", account_id=ap.id))
    db.commit()
    return db, warehouse, user, products, inventory, expense, supplier


def create(data, *, items=None, warehouse=True):
    db, wh, user, products, _, _, supplier = data
    return Service.create(db, user=user, data=GoodsReceiptCreate(
        supplier_id=supplier.id, business_unit_id=user.default_business_unit_id,
        location_id=user.location_id, department_id=user.default_department_id,
        warehouse_id=wh.id if warehouse else None,
        items=items or [dict(product_id=p.id, quantity=2, unit_cost=10) for p in products],
    ))


def test_mixed_master_defaults_post_only_stock_lines_and_keep_balanced_journal(stock_db):
    data = setup_receiving(stock_db); db, wh, user, products, balances, expense, _ = data
    receipt = create(data)
    assert receipt.destination_type == "MIXED"
    assert [x.destination_type for x in receipt.items] == ["WAREHOUSE", "DIRECT_USE"]
    assert receipt.items[1].expense_account_id == expense.id
    Service.post(db, receipt_id=receipt.id, user=user)
    assert [Decimal(x.quantity) for x in balances] == [Decimal("22"), Decimal("10.1250")]
    movements = db.query(StockMovement).all()
    assert len(movements) == 1 and movements[0].product_id == products[0].id
    journal = db.query(JournalEntry).filter_by(reference_type="GOODS_RECEIPT").one()
    assert {x.account_id for x in journal.lines} >= {products[0].inventory_account_id, expense.id}
    assert sum(x.debit for x in journal.lines) == sum(x.credit for x in journal.lines) == 40
    assert db.query(GeneralLedger).count() == 0  # Existing finance posting stage stays separate.
    Service.return_receipt(db, receipt_id=receipt.id, user=user)
    assert [Decimal(x.quantity) for x in balances] == [Decimal("20"), Decimal("10.1250")]
    assert {x.product_id for x in db.query(StockMovement).all()} == {products[0].id}
    assert journal.status == "VOID"


def test_only_direct_use_does_not_require_or_store_warehouse(stock_db):
    data = setup_receiving(stock_db); db, wh, user, products, balances, *_ = data
    receipt = create(data, warehouse=False, items=[dict(product_id=products[1].id, quantity=2, unit_cost=10)])
    assert receipt.destination_type == "DIRECT_USE" and receipt.warehouse_id is None
    Service.post(db, receipt_id=receipt.id, user=user)
    assert db.query(StockMovement).count() == 0
    assert Decimal(balances[1].quantity) == Decimal("10.1250")


def test_direct_receipt_can_repeat_product_at_different_costs(stock_db):
    data = setup_receiving(stock_db)
    db, _, user, products, balances, *_ = data
    product = products[0]
    starting_quantity = Decimal(balances[0].quantity)
    starting_value = starting_quantity * Decimal(balances[0].average_cost)
    receipt = create(data, items=[
        dict(product_id=product.id, quantity=2, unit_cost=10),
        dict(product_id=product.id, quantity=3, unit_cost=14),
    ])
    assert len(receipt.items) == 2
    assert [Decimal(item.unit_cost) for item in receipt.items] == [Decimal("10"), Decimal("14")]
    assert Decimal(receipt.subtotal) == Decimal("62")

    Service.post(db, receipt_id=receipt.id, user=user)
    movements = db.query(StockMovement).order_by(StockMovement.id).all()
    assert len(movements) == 2
    assert len({row.goods_receipt_item_id for row in movements}) == 2
    assert [Decimal(row.unit_cost) for row in movements] == [Decimal("10"), Decimal("14")]
    assert Decimal(balances[0].quantity) == starting_quantity + 5
    assert abs(Decimal(balances[0].average_cost) - (starting_value + 62) / (starting_quantity + 5)) < Decimal("0.0001")

    journal = db.query(JournalEntry).filter_by(reference_type="GOODS_RECEIPT").one()
    assert sum(Decimal(line.debit) for line in journal.lines) == Decimal("62")
    assert sum(Decimal(line.credit) for line in journal.lines) == Decimal("62")


def test_explicit_stock_exception_requires_reason_and_keeps_master(stock_db):
    data = setup_receiving(stock_db); db, wh, user, products, *_ = data
    payload = dict(product_id=products[1].id, quantity=3, unit_cost=10, destination_type="WAREHOUSE")
    with pytest.raises(HTTPException) as exc:
        create(data, items=[payload])
    assert "reason" in exc.value.detail
    db.rollback()
    payload["destination_override_reason"] = "Frozen batch stored for later use"
    receipt = create(data, items=[payload])
    assert receipt.items[0].destination_override_reason == payload["destination_override_reason"]
    assert products[1].inventory_treatment == "DIRECT_USE"
    Service.post(db, receipt_id=receipt.id, user=user)
    assert db.query(StockMovement).one().product_id == products[1].id


def test_direct_use_override_uses_expense_without_stock(stock_db):
    data = setup_receiving(stock_db); db, _, user, products, balances, expense, _ = data
    receipt = create(data, warehouse=False, items=[dict(product_id=products[0].id, quantity=2, unit_cost=10, destination_type="DIRECT_USE", destination_override_reason="Used immediately by kitchen")])
    assert receipt.items[0].expense_account_id == expense.id
    Service.post(db, receipt_id=receipt.id, user=user)
    assert db.query(StockMovement).count() == 0 and balances[0].quantity == 20


def test_edit_preserves_unedited_destinations_and_can_reset_exception(stock_db):
    data = setup_receiving(stock_db); db, _, user, products, *_ = data
    receipt = create(data, items=[dict(product_id=products[0].id, quantity=2, unit_cost=10, destination_type="DIRECT_USE", destination_override_reason="Immediate use")], warehouse=False)
    line = receipt.items[0]
    base = dict(received_at=receipt.received_at, items=[dict(item_id=line.id, quantity=3, unit_cost=10, is_taxable=False)])
    Service.update(db, receipt=receipt, data=GoodsReceiptUpdate(**base), user=user)
    assert line.destination_type == "DIRECT_USE" and line.destination_override_reason == "Immediate use"
    base["warehouse_id"] = data[1].id
    base["items"][0]["destination_type"] = None  # Explicitly follow current Item Master.
    Service.update(db, receipt=receipt, data=GoodsReceiptUpdate(**base), user=user)
    assert line.destination_type == "WAREHOUSE" and line.destination_override_reason is None


def test_legacy_route_does_not_follow_changed_master():
    product = SimpleNamespace(code="LEGACY", inventory_treatment="DIRECT_USE")
    item = SimpleNamespace(product=product, destination_type=None)
    receipt = SimpleNamespace(destination_type="WAREHOUSE", items=[item])
    assert master_destination(product) == "DIRECT_USE"
    assert line_destination(receipt, item) == "WAREHOUSE"


def test_fixed_asset_stays_capitalized_and_nonstock_cannot_be_forced_into_stock():
    for treatment in ["FIXED_ASSET", "NON_STOCK"]:
        product = SimpleNamespace(code="SPECIAL", inventory_treatment=treatment)
        with pytest.raises(HTTPException): resolve_destination(product, "WAREHOUSE", "Special case")
        assert resolve_destination(product)[0] == "DIRECT_USE"


def test_mixed_cost_correction_only_revalues_warehouse_line(stock_db):
    data = setup_receiving(stock_db); db, _, user, _, balances, *_ = data
    receipt = create(data); Service.post(db, receipt_id=receipt.id, user=user)
    old = [(x.quantity, x.average_cost) for x in balances]
    Service.correct_costs(db, receipt_id=receipt.id, user=user, data=GoodsReceiptCostCorrection(reason="Corrected vendor price", items=[dict(item_id=receipt.items[1].id, unit_cost=15)]))
    assert [(x.quantity, x.average_cost) for x in balances] == old
    Service.correct_costs(db, receipt_id=receipt.id, user=user, data=GoodsReceiptCostCorrection(reason="Corrected stock price", items=[dict(item_id=receipt.items[0].id, unit_cost=12)]))
    assert balances[0].average_cost != old[0][1]
    assert balances[1].average_cost == old[1][1]
    assert db.query(StockMovement).one().unit_cost == 12


def test_invoice_snapshots_respect_each_mixed_receipt_line(stock_db):
    from app.models.supplier_invoice import SupplierInvoice, SupplierInvoiceLine
    from datetime import date
    data = setup_receiving(stock_db); db, _, user, products, _, expense, supplier = data
    receipt = create(data)
    invoice = SupplierInvoice(internal_invoice_number="TEST-MIXED", supplier_invoice_number="MIXED", supplier_id=supplier.id, invoice_date=date.today(), goods_receipt_id=receipt.id, business_unit_id=receipt.business_unit_id, location_id=receipt.location_id, department_id=receipt.department_id, subtotal=40, total_amount=40)
    db.add(invoice); db.flush()
    for item in receipt.items:
        line = SupplierInvoiceLine(supplier_invoice_id=invoice.id, product_id=item.product_id, goods_receipt_item_id=item.id, description=item.product.name, quantity=2, unit_price=10, line_amount=20)
        db.add(line);db.flush()
        account = DirectCoaService(db).snapshot_invoice_line(invoice, line)
        assert account.id == (products[0].inventory_account_id if item.product_id == products[0].id else expense.id)
