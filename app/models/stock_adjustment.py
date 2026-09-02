from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class StockAdjustment(Base, TimestampMixin):
    __tablename__ = "stock_adjustments"

    id: Mapped[int] = mapped_column(primary_key=True)
    adjustment_number: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(30), default="DRAFT", index=True, nullable=False
    )
    adjustment_date: Mapped[date] = mapped_column(
        Date, default=date.today, nullable=False
    )
    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    business_unit_id: Mapped[int | None] = mapped_column(
        ForeignKey("business_units.id", ondelete="RESTRICT"), index=True
    )
    location_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"), index=True
    )
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"), index=True
    )
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    posted_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    total_adjustment_value: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0"), nullable=False
    )

    warehouse = relationship("Warehouse")
    business_unit = relationship("BusinessUnit")
    location = relationship("Location")
    department = relationship("Department")
    created_by = relationship("User", foreign_keys=[created_by_id])
    posted_by = relationship("User", foreign_keys=[posted_by_id])
    items = relationship(
        "StockAdjustmentItem",
        back_populates="stock_adjustment",
        cascade="all, delete-orphan",
    )


class StockAdjustmentItem(Base):
    __tablename__ = "stock_adjustment_items"
    __table_args__ = (
        UniqueConstraint(
            "stock_adjustment_id",
            "product_id",
            name="uq_stock_adjustment_product",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_adjustment_id: Mapped[int] = mapped_column(
        ForeignKey("stock_adjustments.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    system_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    adjusted_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    delta_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(14, 4), default=Decimal("0"), nullable=False
    )
    uom: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(1000))
    line_value: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0"), nullable=False
    )

    stock_adjustment = relationship("StockAdjustment", back_populates="items")
    product = relationship("Product")