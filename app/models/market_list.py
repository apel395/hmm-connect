from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class MarketList(Base, TimestampMixin):
    __tablename__ = "market_lists"

    id: Mapped[int] = mapped_column(primary_key=True)
    ml_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", nullable=False)
    request_date: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), default="LIVE", nullable=False)
    external_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    business_unit_id: Mapped[int | None] = mapped_column(ForeignKey("business_units.id", ondelete="SET NULL"), nullable=True, index=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id", ondelete="SET NULL"), nullable=True, index=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    requested_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    business_unit = relationship("BusinessUnit")
    location = relationship("Location")
    department = relationship("Department")
    requested_by = relationship("User")
    items = relationship("MarketListItem", back_populates="market_list", cascade="all, delete-orphan")
    purchase_orders = relationship("PurchaseOrder", back_populates="market_list")


class MarketListItem(Base):
    __tablename__ = "market_list_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    market_list_id: Mapped[int] = mapped_column(ForeignKey("market_lists.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    estimated_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total_price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    is_taxable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0, nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)

    market_list = relationship("MarketList", back_populates="items")
    product = relationship("Product")

    @property
    def product_code(self) -> str:
        return self.product.code

    @property
    def product_name(self) -> str:
        return self.product.name

    @property
    def product_uom(self) -> str:
        return self.product.uom
