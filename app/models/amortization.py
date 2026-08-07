from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Amortization(Base):
    __tablename__ = "amortizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    amortization_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_date: Mapped[date] = mapped_column(Date, index=True)
    original_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    useful_life_months: Mapped[int] = mapped_column(Integer, nullable=False)
    months_posted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    accumulated_amortization: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    net_book_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", index=True, nullable=False)

    business_unit_id: Mapped[int] = mapped_column(ForeignKey("business_units.id"), index=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"), nullable=True, index=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), nullable=True, index=True)

    asset_account_id: Mapped[int] = mapped_column(ForeignKey("chart_of_accounts.id"))
    accumulated_amortization_account_id: Mapped[int] = mapped_column(ForeignKey("chart_of_accounts.id"))
    amortization_expense_account_id: Mapped[int] = mapped_column(ForeignKey("chart_of_accounts.id"))

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
