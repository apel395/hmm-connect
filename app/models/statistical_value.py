"""Non-financial operational quantities; never journal or GL entries."""
from datetime import date
from decimal import Decimal
from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class StatisticalValue(Base, TimestampMixin):
    __tablename__ = "statistical_values"
    __table_args__ = (
        CheckConstraint("actual IS NULL OR actual >= 0", name="ck_stat_actual_positive"),
        CheckConstraint("budget IS NULL OR budget >= 0", name="ck_stat_budget_positive"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("chart_of_accounts.id"), index=True)
    period: Mapped[date] = mapped_column(Date, index=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), index=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"))
    unit: Mapped[str] = mapped_column(String(30))
    actual: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    budget: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    account = relationship("ChartOfAccount")
    location = relationship("Location")
    department = relationship("Department")


Index("uq_statistical_value_scope", StatisticalValue.account_id, StatisticalValue.period,
      StatisticalValue.location_id, func.coalesce(StatisticalValue.department_id, 0), unique=True)
