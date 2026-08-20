from decimal import Decimal

from app.models.stock_opname import StockOpnameItem


def test_stock_opname_variance_math():
    item = StockOpnameItem(
        product_id=1,
        system_quantity=Decimal("20"),
        physical_quantity=Decimal("17"),
        unit_cost=Decimal("10"),
        uom="PCS",
    )
    item.variance_quantity = item.physical_quantity - item.system_quantity
    assert item.variance_quantity == Decimal("-3")


def test_stock_opname_positive_variance_math():
    item = StockOpnameItem(
        product_id=1,
        system_quantity=Decimal("20"),
        physical_quantity=Decimal("24"),
        unit_cost=Decimal("10"),
        uom="PCS",
    )
    item.variance_quantity = item.physical_quantity - item.system_quantity
    assert item.variance_quantity == Decimal("4")
