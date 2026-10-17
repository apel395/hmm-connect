"""Stock visibility retains historical anchors and negative balances."""
from datetime import date, datetime, timezone
from decimal import Decimal

from test_store_request_flow import store_db
from app.api.v1.inventory import list_inventory
from app.models.inventory import Inventory
from app.models.stock_movement import StockMovement


def report(db, user, **kwargs):
    return list_inventory(db=db, user=user, health=None, search=None,
                          page=1, page_size=50, **kwargs)


def test_default_hides_empty_rows_but_preserves_totals_and_snapshots(store_db):
    db, _, _, _, warehouse, _, user, products = store_db
    db.add_all([
        Inventory(product_id=products[0].id, warehouse_id=warehouse.id, quantity=0, average_cost=30),
        Inventory(product_id=products[1].id, warehouse_id=warehouse.id, quantity=4, average_cost=10),
    ])
    db.commit()
    result = report(db, user)
    assert [row['product_id'] for row in result['items']] == [products[1].id]
    assert result['total_items'] == result['summary']['stock_lines'] == 1
    assert result['summary']['stock_value'] == Decimal('40')
    assert result['totals_by_account'][0]['stock_value'] == Decimal('40')
    expanded = report(db, user, show_empty=True)
    assert expanded['total_items'] == 2
    assert expanded['summary']['stock_value'] == result['summary']['stock_value']
    assert db.query(Inventory).count() == 2


def test_reorder_keeps_empty_monitored_items_and_negative_stock_stays_visible(store_db):
    db, _, _, _, warehouse, _, user, products = store_db
    products[0].minimum_stock = 5
    db.add_all([
        Inventory(product_id=products[0].id, warehouse_id=warehouse.id, quantity=0, average_cost=10),
        Inventory(product_id=products[1].id, warehouse_id=warehouse.id, quantity=-2, average_cost=10),
    ])
    db.commit()
    assert [row['product_id'] for row in report(db, user)['items']] == [products[1].id]
    for health in ('LOW_STOCK', 'REORDER', 'BELOW_MINIMUM'):
        result = list_inventory(db=db, user=user, health=health, search=None, page=1, page_size=50)
        assert [row['product_id'] for row in result['items']] == [products[0].id]
        assert result['summary']['needs_reorder'] == 1


def test_as_of_uses_historical_quantity_not_current_zero(store_db):
    db, bu, dept, location, warehouse, _, user, products = store_db
    db.add(Inventory(product_id=products[0].id, warehouse_id=warehouse.id, quantity=0, average_cost=10))
    db.add(StockMovement(product_id=products[0].id, warehouse_id=warehouse.id,
                         business_unit_id=bu.id, location_id=location.id, department_id=dept.id,
                         movement_type='OUT', quantity=3, unit_cost=10,
                         created_at=datetime(2026, 2, 10, tzinfo=timezone.utc)))
    db.commit()
    result = report(db, user, as_of=date(2026, 1, 31))
    assert result['total_items'] == 1
    assert result['items'][0]['quantity'] == Decimal('3')
    assert result['summary']['stock_value'] == Decimal('30')
    assert report(db, user)['total_items'] == 0
    assert db.query(StockMovement).count() == 1
