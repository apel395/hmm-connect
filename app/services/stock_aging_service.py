"""Age stock still on hand using the receipt layers left after FIFO consumption.

The inventory table stores a quantity and average cost, not physical lots. FIFO
here is an aging estimate; its layers do not change stock valuation or posting.
Any on-hand quantity beyond recorded 2026 receipts belongs to the manually
entered 2026 opening stock and is dated 2026-01-01 for this report.
"""

from calendar import monthrange
from datetime import date
from decimal import Decimal
from typing import Iterable


START_DATE = date(2026, 1, 1)


def six_month_cutoff(as_of: date) -> date:
    month_index = as_of.year * 12 + as_of.month - 1 - 6
    year, month = divmod(month_index, 12)
    month += 1
    return date(year, month, min(as_of.day, monthrange(year, month)[1]))


def age_remaining_stock(
    quantity: Decimal,
    inbound_layers: Iterable[tuple[date | str, Decimal]],
    as_of: date,
) -> dict:
    remaining = max(Decimal(quantity or 0), Decimal("0"))
    if remaining == 0:
        return {
            "movement_class": "EMPTY", "oldest_stock_date": None,
            "stock_age_days": None,
            "aging_quantities": {label: Decimal("0") for label in ("FAST", "SLOW", "DEAD")},
        }

    buckets = {label: Decimal("0") for label in ("FAST", "SLOW", "DEAD")}
    oldest = None

    def category(day: date) -> str:
        days = (as_of - day).days
        return "FAST" if days <= 30 else "SLOW" if day >= six_month_cutoff(as_of) else "DEAD"

    for day, received in sorted(
        inbound_layers,
        key=lambda layer: layer[0] if isinstance(layer[0], date) else date.fromisoformat(layer[0]),
        reverse=True,
    ):
        day = day if isinstance(day, date) else date.fromisoformat(day)
        received = Decimal(received or 0)
        if day > as_of or received <= 0:
            continue
        used = min(remaining, received)
        buckets[category(day)] += used
        remaining -= used
        oldest = day
        if remaining == 0:
            break

    if remaining > 0:
        oldest = min(START_DATE, as_of)
        buckets[category(oldest)] += remaining

    return {
        "movement_class": category(oldest),
        "oldest_stock_date": oldest,
        "stock_age_days": (as_of - oldest).days,
        "aging_quantities": buckets,
    }
