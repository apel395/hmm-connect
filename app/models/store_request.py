from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text
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
    issues = relationship("StoreIssue", back_populates="store_request", cascade="all, delete-orphan")


class StoreRequestItem(Base):
    __tablename__ = "store_request_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_request_id: Mapped[int] = mapped_column(ForeignKey("store_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True)
    requested_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    issued_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    uom: Mapped[str] = mapped_column(String(30), nullable=False)

    store_request = relationship("StoreRequest", back_populates="items")
    product = relationship("Product")


class StoreIssue(Base, TimestampMixin):
    __tablename__ = "store_issues"

    id: Mapped[int] = mapped_column(primary_key=True)
    issue_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    store_request_id: Mapped[int] = mapped_column(ForeignKey("store_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    posted_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    store_request = relationship("StoreRequest", back_populates="issues")
    created_by = relationship("User", foreign_keys=[created_by_id])
    posted_by = relationship("User", foreign_keys=[posted_by_id])
    items = relationship("StoreIssueItem", back_populates="issue", cascade="all, delete-orphan")


class StoreIssueItem(Base):
    __tablename__ = "store_issue_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("store_issues.id", ondelete="CASCADE"), nullable=False, index=True)
    store_request_item_id: Mapped[int] = mapped_column(ForeignKey("store_request_items.id", ondelete="RESTRICT"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    issue = relationship("StoreIssue", back_populates="items")
    store_request_item = relationship("StoreRequestItem")
    product = relationship("Product")
