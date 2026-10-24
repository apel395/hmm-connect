"""Outlet operations: no inventory or opening-balance accounting."""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Integer, Numeric, ForeignKey, DateTime, Boolean, Text, Index, CheckConstraint, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class PosOutletPolicy(Base):
    __tablename__ = 'pos_outlet_policies'
    __table_args__ = (UniqueConstraint('location_id', 'department_id', name='uq_pos_outlet_policy'), CheckConstraint("order_mode IN ('TABLE','COUNTER','EVENT')", name='ck_pos_order_mode'))
    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(ForeignKey('locations.id', ondelete='RESTRICT'))
    department_id: Mapped[int] = mapped_column(ForeignKey('departments.id', ondelete='RESTRICT'))
    order_mode: Mapped[str] = mapped_column(String(10), nullable=False)


class PosTable(Base):
    __tablename__ = 'pos_tables'
    __table_args__ = (UniqueConstraint('location_id', 'department_id', 'name', name='uq_pos_table_name'), CheckConstraint('seats > 0', name='ck_pos_table_seats'))
    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(ForeignKey('locations.id', ondelete='RESTRICT'), index=True)
    department_id: Mapped[int] = mapped_column(ForeignKey('departments.id', ondelete='RESTRICT'), index=True)
    name: Mapped[str] = mapped_column(String(30), nullable=False)
    seats: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class PosCashierSession(Base):
    __tablename__ = 'pos_cashier_sessions'
    __table_args__ = (
        Index('uq_pos_open_cashier', 'location_id', 'department_id', 'cashier_id', unique=True,
              postgresql_where=text("status = 'OPEN'"), sqlite_where=text("status = 'OPEN'")),
        CheckConstraint("status IN ('OPEN','CLOSED')", name='ck_pos_session_status'),
        CheckConstraint('opening_cash >= 0', name='ck_pos_opening_cash'),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(ForeignKey('locations.id', ondelete='RESTRICT'), index=True)
    department_id: Mapped[int] = mapped_column(ForeignKey('departments.id', ondelete='RESTRICT'), index=True)
    cashier_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'), index=True)
    status: Mapped[str] = mapped_column(String(10), default='OPEN', nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    opening_cash: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_by_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'))
    counted_cash: Mapped[Decimal | None] = mapped_column(Numeric(18,2))
    expected_cash: Mapped[Decimal | None] = mapped_column(Numeric(18,2))
    cash_difference: Mapped[Decimal | None] = mapped_column(Numeric(18,2))
    difference_reason: Mapped[str | None] = mapped_column(Text)
