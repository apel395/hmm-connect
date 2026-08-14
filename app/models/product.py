from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(150))
    group_code: Mapped[str] = mapped_column(String(10))
    group_name: Mapped[str] = mapped_column(String(50))
    subgroup_code: Mapped[str] = mapped_column(String(10))
    subgroup_name: Mapped[str] = mapped_column(String(100))
    uom: Mapped[str] = mapped_column(String(20))
    usage_uom: Mapped[str] = mapped_column(String(20))
    conversion: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=1)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cost_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    selling_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)

    # Item master is the default source of truth for PPN treatment.
    # Transaction lines snapshot these values so historical documents remain stable
    # when Finance changes the item master later.
    tax_category: Mapped[str] = mapped_column(String(30), default="REVIEW_REQUIRED", nullable=False)
    is_taxable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0, nullable=False)
    tax_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tax_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)

    minimum_stock: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    reorder_level: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    maximum_stock: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    lead_time_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    preferred_supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    inventory_account_id: Mapped[int | None] = mapped_column(ForeignKey("chart_of_accounts.id"), nullable=True)
    purchase_account_id: Mapped[int | None] = mapped_column(ForeignKey("chart_of_accounts.id"), nullable=True)
    cogs_account_id: Mapped[int | None] = mapped_column(ForeignKey("chart_of_accounts.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    inventory = relationship("Inventory", back_populates="product", cascade="all, delete-orphan")
    suppliers = relationship("SupplierProduct", back_populates="product", cascade="all, delete-orphan")
