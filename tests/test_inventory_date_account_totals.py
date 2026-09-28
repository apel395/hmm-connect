from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.inventory import list_inventory, list_movements
from app.models import Base
from app.models.chart_of_account import ChartOfAccount
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.stock_movement import StockMovement
from app.models.warehouse import Warehouse


ADMIN = SimpleNamespace(
    id=1, roles=[SimpleNamespace(name="SYSTEM_ADMINISTRATOR")],
    default_location_id=None, location_id=None,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()
    engine.dispose()


def test_inventory_as_of_and_movement_account_totals_include_all_pages(db):
    account = ChartOfAccount(
        account_number="100-300-100", account_name="Food Inventory",
        account_type="ASSET", normal_balance="DEBIT",
        is_active=True, is_posting=True,
    )
    product = Product(
        code="ITEM-1", name="Food", group_code="1", group_name="Food",
        subgroup_code="1", subgroup_name="Food", uom="PCS",
        usage_uom="PCS", is_active=True,
    )
    warehouse = Warehouse(code="WH-1", name="Warehouse", is_active=True)
    db.add_all([account, product, warehouse])
    db.flush()
    product.inventory_account_id = account.id
    db.add(Inventory(product_id=product.id, warehouse_id=warehouse.id,
                     quantity=Decimal("7"), average_cost=Decimal("10")))
    for day, kind, quantity in ((2, "IN", "5"), (3, "OUT", "2"), (10, "IN", "4")):
        db.add(StockMovement(
            product_id=product.id, warehouse_id=warehouse.id,
            inventory_account_id=account.id, movement_type=kind,
            quantity=Decimal(quantity), unit_cost=Decimal("10"),
            created_at=datetime(2026, 1, day, tzinfo=timezone.utc),
        ))
    db.commit()

    inventory = list_inventory(
        warehouse_id=None, account_id=None, location_id=None,
        as_of=date(2026, 1, 3), health=None, search=None,
        page=1, page_size=1, db=db, user=ADMIN,
    )
    assert inventory["items"][0]["quantity"] == Decimal("3")
    assert inventory["summary"]["stock_value"] == Decimal("30")
    assert inventory["totals_by_account"][0]["quantity"] == Decimal("3")

    movements = list_movements(
        product_id=None, warehouse_id=None, purchase_order_id=None,
        goods_receipt_id=None, location_id=None, department_id=None,
        account_id=account.id, date_from=date(2026, 1, 3),
        date_to=date(2026, 1, 10), search=None,
        page=1, page_size=1, db=db, user=ADMIN,
    )
    assert movements["total_items"] == 2
    assert len(movements["items"]) == 1
    assert movements["summary"]["in_qty"] == Decimal("4")
    assert movements["summary"]["out_qty"] == Decimal("2")
    assert movements["summary"]["net_value"] == Decimal("20")
    assert movements["totals_by_account"][0]["net_qty"] == Decimal("2")
    assert movements["items"][0]["movement_date"] == "2026-01-10"


def test_movement_rejects_reversed_dates(db):
    with pytest.raises(HTTPException) as error:
        list_movements(
            product_id=None, warehouse_id=None, purchase_order_id=None,
            goods_receipt_id=None, location_id=None, department_id=None,
            account_id=None, date_from=date(2026, 1, 2),
            date_to=date(2026, 1, 1), search=None,
            page=1, page_size=10, db=db, user=ADMIN,
        )
    assert error.value.status_code == 422
