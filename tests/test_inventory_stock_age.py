from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.inventory import list_inventory
from app.models import Base
from app.models.chart_of_account import ChartOfAccount
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.stock_movement import StockMovement
from app.models.warehouse import Warehouse


def test_inventory_classification_ages_remaining_stock_and_filters_consistently():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        account = ChartOfAccount(
            account_number="100-300-100", account_name="Food Inventory",
            account_type="ASSET", normal_balance="DEBIT",
            is_active=True, is_posting=True,
        )
        warehouse = Warehouse(code="WH-AGE", name="Aging warehouse", is_active=True)
        db.add_all([account, warehouse])
        db.flush()
        for code, remaining, outbound in (("OLD", "11", "4"), ("FRESH", "2", "13")):
            product = Product(
                code=code, name=code, group_code="1", group_name="Food",
                subgroup_code="1", subgroup_name="Food", uom="PCS",
                usage_uom="PCS", is_active=True, inventory_account_id=account.id,
            )
            db.add(product)
            db.flush()
            db.add(Inventory(product_id=product.id, warehouse_id=warehouse.id,
                             quantity=Decimal(remaining), average_cost=Decimal("10")))
            for day, kind, qty in (
                (date(2026, 1, 15), "IN", "10"),
                (date(2026, 9, 25), "IN", "5"),
                (date(2026, 9, 30), "OUT", outbound),
            ):
                db.add(StockMovement(
                    product_id=product.id, warehouse_id=warehouse.id,
                    inventory_account_id=account.id, movement_type=kind,
                    quantity=Decimal(qty), unit_cost=Decimal("10"),
                    created_at=datetime(day.year, day.month, day.day, tzinfo=timezone.utc),
                ))
        db.commit()

        user = SimpleNamespace(
            id=1, roles=[SimpleNamespace(name="SYSTEM_ADMINISTRATOR")],
            default_location_id=None, location_id=None,
        )
        common = dict(
            warehouse_id=None, account_id=None, location_id=None,
            as_of=date(2026, 10, 1), health=None, search=None,
            page=1, page_size=1, db=db, user=user,
        )
        dead = list_inventory(movement_class="DEAD", **common)
        assert dead["total_items"] == 1
        assert dead["items"][0]["product_code"] == "OLD"
        assert dead["items"][0]["stock_age_days"] > 90
        assert dead["summary"]["movement_classes"]["FAST"]["stock_lines"] == 1
        assert dead["summary"]["movement_classes"]["DEAD"]["stock_lines"] == 1
        assert dead["summary"]["stock_value"] == Decimal("110")
        assert dead["totals_by_account"][0]["quantity"] == Decimal("11")

        fresh = list_inventory(movement_class="FAST", **common)
        assert fresh["items"][0]["product_code"] == "FRESH"
        assert fresh["summary"]["stock_value"] == Decimal("20")
    finally:
        db.close()
        engine.dispose()
