"""Currency value snapshots for return events; legacy movements retain their original basis."""
from decimal import Decimal
from sqlalchemy import case, func, Numeric, type_coerce
from app.models.stock_movement import StockMovement


def sql_movement_value():
    return type_coerce(func.coalesce(StockMovement.recorded_value, func.abs(StockMovement.quantity) * func.coalesce(StockMovement.unit_cost, 0)), Numeric(32, 8))


def sql_signed_movement_value():
    amount = sql_movement_value()
    return case((StockMovement.movement_type == 'OUT', -amount), else_=amount)


def movement_value(row):
    return Decimal(row.recorded_value) if row.recorded_value is not None else abs(Decimal(row.quantity or 0)) * Decimal(row.unit_cost or 0)
