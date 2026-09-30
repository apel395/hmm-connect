from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.inventory import inventory_accounts, list_inventory
from app.models import Base
from app.models.chart_of_account import ChartOfAccount
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.stock_movement import StockMovement
from app.models.warehouse import Warehouse


def test_stock_velocity_uses_outbound_age_at_selected_date_and_inventory_coa_only():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    user = SimpleNamespace(roles=[SimpleNamespace(name="SYSTEM_ADMINISTRATOR")],
                           default_location_id=None, location_id=None)
    try:
        stock_account = ChartOfAccount(
            account_number="100-300-100", account_name="Inventory",
            account_type="ASSET", normal_balance="DEBIT",
            is_active=True, is_posting=True,
        )
        cash_account = ChartOfAccount(
            account_number="100-100-100", account_name="Cash",
            account_type="ASSET", normal_balance="DEBIT",
            is_active=True, is_posting=True,
        )
        warehouse = Warehouse(code="VELOCITY-WH", name="Warehouse", is_active=True)
        db.add_all([stock_account, cash_account, warehouse])
        db.flush()
        cases = [
            ("FAST-ITEM", date(2026, 9, 5), "OUT"),
            ("SLOW-ITEM", date(2026, 8, 10), "IN"),
            ("DEAD-ITEM", date(2026, 3, 1), "IN"),
        ]
        for code, movement_date, kind in cases:
            product = Product(code=code, name=code, group_code="1", group_name="Food",
                              subgroup_code="1", subgroup_name="Food", uom="PCS",
                              usage_uom="PCS", is_active=True,
                              inventory_account_id=stock_account.id)
            db.add(product)
            db.flush()
            db.add(Inventory(product_id=product.id, warehouse_id=warehouse.id,
                             quantity=Decimal("5"), average_cost=Decimal("10")))
            db.add(StockMovement(
                product_id=product.id, warehouse_id=warehouse.id,
                inventory_account_id=stock_account.id,
                movement_type=kind, quantity=Decimal("1"), unit_cost=Decimal("10"),
                created_at=datetime(movement_date.year, movement_date.month,
                                    movement_date.day, tzinfo=timezone.utc),
            ))
        db.commit()

        params = dict(warehouse_id=None, account_id=None, location_id=None,
                      as_of=date(2026, 9, 30), health=None, search=None,
                      page=1, page_size=10, db=db, user=user)
        all_stock = list_inventory(**params)
        assert {row["product_code"]: row["movement_class"]
                for row in all_stock["items"]} == {
                    "FAST-ITEM": "FAST", "SLOW-ITEM": "SLOW", "DEAD-ITEM": "DEAD",
                }
        assert [all_stock["summary"]["movement_classes"][label]["stock_lines"]
                for label in ("FAST", "SLOW", "DEAD")] == [1, 1, 1]
        fast = list_inventory(**params, movement_class="FAST")
        assert [row["product_code"] for row in fast["items"]] == ["FAST-ITEM"]
        assert fast["summary"]["stock_value"] == Decimal("50")
        assert [row["account_number"] for row in inventory_accounts(db=db, user=user)] == [
            "100-300-100"
        ]
    finally:
        db.close()
        engine.dispose()
