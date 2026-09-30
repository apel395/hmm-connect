from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.chart_of_account import ChartOfAccount
from app.models.goods_receipt import GoodsReceipt, GoodsReceiptItem
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.stock_movement import StockMovement
from app.models.warehouse import Warehouse
from scripts import rebase_2026_inventory_average_cost as repair


@pytest.fixture
def stock(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    monkeypatch.setattr(repair, "TARGETS", (
        repair.Target("TEST-2026", Decimal("5"), Decimal("10"), Decimal("60"), 1),
    ))
    monkeypatch.setattr(repair, "EXPECTED_GAP", Decimal("10"))
    account = ChartOfAccount(
        account_number="100-300-100", account_name="Food Inventory",
        account_type="ASSET", normal_balance="DEBIT", is_active=True, is_posting=True,
    )
    warehouse = Warehouse(code="WH-005", name="Warehouse", is_active=True)
    other_warehouse = Warehouse(code="WH-006", name="Other Warehouse", is_active=True)
    product = Product(
        code="TEST-2026", name="Test", group_code="1", group_name="Food",
        subgroup_code="1", subgroup_name="Food", uom="PCS", usage_uom="PCS",
        is_active=True,
    )
    db.add_all([account, warehouse, other_warehouse, product])
    db.flush()
    product.inventory_account_id = account.id
    inventory = Inventory(product_id=product.id, warehouse_id=warehouse.id,
                          quantity=Decimal("5"), average_cost=Decimal("10"))
    other_inventory = Inventory(product_id=product.id, warehouse_id=other_warehouse.id,
                                quantity=Decimal("1"), average_cost=Decimal("8"))
    receipt = GoodsReceipt(
        receipt_number="GR-TEST-2026", warehouse_id=warehouse.id,
        destination_type="WAREHOUSE", status="POSTED",
        received_at=datetime(2026, 1, 17, tzinfo=timezone.utc),
    )
    item = GoodsReceiptItem(product_id=product.id, quantity=Decimal("5"),
                            unit_cost=Decimal("12"))
    receipt.items.append(item)
    db.add_all([inventory, other_inventory, receipt])
    db.flush()
    movement = StockMovement(
        product_id=product.id, warehouse_id=warehouse.id,
        goods_receipt_id=receipt.id, goods_receipt_item_id=item.id,
        inventory_account_id=account.id, movement_type="IN",
        reference_type="GOODS_RECEIPT", reference_id=receipt.id,
        quantity=Decimal("5"), unit_cost=Decimal("12"),
    )
    db.add(movement)
    db.commit()
    yield db, inventory, receipt, movement, other_inventory
    db.close()
    engine.dispose()


def test_preview_then_apply_repairs_only_the_stale_average(stock):
    db, inventory, receipt, movement, other_inventory = stock
    preview = repair.execute(db)
    assert preview[0].new_average == Decimal("12.0000")
    assert db.get(Inventory, inventory.id).average_cost == Decimal("10")

    applied = repair.execute(db, apply=True)
    assert applied == preview
    db.refresh(inventory)
    assert inventory.quantity == Decimal("5")
    assert inventory.average_cost == Decimal("12")
    assert db.get(StockMovement, movement.id).unit_cost == Decimal("12")
    assert db.get(GoodsReceipt, receipt.id).status == "POSTED"
    assert db.get(Inventory, other_inventory.id).average_cost == Decimal("8")


def test_refuses_a_changed_receipt_and_rolls_back(stock):
    db, inventory, receipt, _, _ = stock
    receipt.status = "DRAFT"
    db.commit()
    with pytest.raises(repair.ChangedStock, match="posted 2026 receipt"):
        repair.execute(db, apply=True)
    db.refresh(inventory)
    assert inventory.average_cost == Decimal("10")


def test_refuses_a_changed_inventory_snapshot(stock):
    db, inventory, _, _, _ = stock
    inventory.quantity = Decimal("6")
    db.commit()
    with pytest.raises(repair.ChangedStock, match="stock snapshot changed"):
        repair.execute(db, apply=True)
    db.refresh(inventory)
    assert inventory.average_cost == Decimal("10")
