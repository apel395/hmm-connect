from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class StoreRequest(Base, TimestampMixin):
    __tablename__ = "store_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    sr_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", nullable=False, index=True)
    request_date: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    business_unit_id: Mapped[int] = mapped_column(ForeignKey("business_units.id", ondelete="RESTRICT"), nullable=False, index=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False, index=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False, index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False, index=True)
    requested_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)

    business_unit = relationship("BusinessUnit")
    department = relationship("Department")
    location = relationship("Location")
    warehouse = relationship("Warehouse")
    requested_by = relationship("User")
    items = relationship("StoreRequestItem", back_populates="store_request", cascade="all, delete-orphan")


class StoreRequestItem(Base):
    __tablename__ = "store_request_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_request_id: Mapped[int] = mapped_column(ForeignKey("store_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True)
    requested_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    issued_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0, nullable=False)
    uom: Mapped[str] = mapped_column(String(30), nullable=False)

    store_request = relationship("StoreRequest", back_populates="items")
    product = relationship("Product")
