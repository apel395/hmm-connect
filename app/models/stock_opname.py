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
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class StockOpname(Base, TimestampMixin):
    __tablename__ = "stock_opnames"
    __table_args__ = (
        Index(
            "uq_stock_opnames_active_warehouse",
            "warehouse_id",
            unique=True,
            postgresql_where=text(
                "status IN ('DRAFT', 'PENDING_APPROVAL', 'APPROVED')"
            ),
            sqlite_where=text(
                "status IN ('DRAFT', 'PENDING_APPROVAL', 'APPROVED')"
            ),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    opname_number: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(30), default="DRAFT", index=True, nullable=False
    )
    count_date: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
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
    created_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    posted_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    warehouse = relationship("Warehouse")
    business_unit = relationship("BusinessUnit")
    location = relationship("Location")
    department = relationship("Department")
    created_by = relationship("User", foreign_keys=[created_by_id])
    posted_by = relationship("User", foreign_keys=[posted_by_id])
    items = relationship(
        "StockOpnameItem", back_populates="stock_opname", cascade="all, delete-orphan"
    )


class StockOpnameItem(Base):
    __tablename__ = "stock_opname_items"
    __table_args__ = (
        UniqueConstraint(
            "stock_opname_id", "product_id", name="uq_stock_opname_product"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_opname_id: Mapped[int] = mapped_column(
        ForeignKey("stock_opnames.id", ondelete="CASCADE"), index=True, nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    system_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    physical_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    variance_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(14, 4), default=0, nullable=False
    )
    uom: Mapped[str] = mapped_column(String(30), nullable=False)

    stock_opname = relationship("StockOpname", back_populates="items")
    product = relationship("Product")
