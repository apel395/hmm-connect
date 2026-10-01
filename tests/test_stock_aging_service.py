from datetime import date
from decimal import Decimal

from app.services.stock_aging_service import age_remaining_stock


def test_recent_outbound_does_not_hide_old_stock_still_on_hand():
    # Old 10 + recent 5 - outbound 4 leaves six old units on hand.
    result = age_remaining_stock(
        Decimal("11"),
        [(date(2026, 1, 15), Decimal("10")), (date(2026, 9, 25), Decimal("5"))],
        date(2026, 10, 1),
    )
    assert result["movement_class"] == "DEAD"
    assert result["oldest_stock_date"] == date(2026, 1, 15)
    assert result["aging_quantities"]["DEAD"] == Decimal("6")
    assert result["aging_quantities"]["FAST"] == Decimal("5")


def test_fifo_outbound_can_exhaust_old_layers():
    result = age_remaining_stock(
        Decimal("2"),
        [(date(2026, 1, 15), Decimal("10")), (date(2026, 9, 25), Decimal("5"))],
        date(2026, 10, 1),
    )
    assert result["movement_class"] == "FAST"
    assert result["oldest_stock_date"] == date(2026, 9, 25)
    assert result["aging_quantities"]["FAST"] == Decimal("2")


def test_unaccounted_receipt_quantity_is_opening_stock():
    result = age_remaining_stock(
        Decimal("7"), [(date(2026, 9, 25), Decimal("3"))], date(2026, 10, 1)
    )
    assert result["movement_class"] == "DEAD"
    assert result["oldest_stock_date"] == date(2026, 1, 1)
    assert result["aging_quantities"]["DEAD"] == Decimal("4")


def test_empty_stock_has_no_age():
    result = age_remaining_stock(Decimal("0"), [], date(2026, 10, 1))
    assert result["movement_class"] == "EMPTY"
    assert result["stock_age_days"] is None
