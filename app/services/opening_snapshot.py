"""User-entered starting balances kept outside journal transactions."""
from datetime import date
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.opening_balance import OpeningBalance


ZERO = Decimal("0.00")


def opening_snapshot(
    db: Session, *, as_of: date, location_id: int | None = None,
    department_id: int | None = None, business_unit_id: int | None = None,
) -> tuple[date | None, dict[int, tuple[Decimal, Decimal]]]:
    """Latest annual snapshot at or before as_of, as debit/credit by account.

    The opening-balance table has a location but no department or business-unit
    dimension. A narrower report must not silently attribute hotel-wide
    starting values to a single department or unit.
    """
    if department_id is not None or business_unit_id is not None:
        return None, {}
    year_query = db.query(func.max(OpeningBalance.fiscal_year)).filter(
        OpeningBalance.fiscal_year <= as_of.year,
    )
    if location_id is not None:
        year_query = year_query.filter(OpeningBalance.location_id == location_id)
    year = year_query.scalar()
    if year is None:
        return None, {}
    q = db.query(
        OpeningBalance.account_id,
        OpeningBalance.balance_type,
        func.sum(OpeningBalance.amount),
    ).filter(OpeningBalance.fiscal_year == year)
    if location_id is not None:
        q = q.filter(OpeningBalance.location_id == location_id)
    result: dict[int, tuple[Decimal, Decimal]] = {}
    for account_id, side, amount in q.group_by(
        OpeningBalance.account_id, OpeningBalance.balance_type,
    ).all():
        debit, credit = result.get(account_id, (ZERO, ZERO))
        if side == "DEBIT":
            debit += Decimal(amount or 0)
        else:
            credit += Decimal(amount or 0)
        result[account_id] = debit, credit
    return date(year, 1, 1), result
