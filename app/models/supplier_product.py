from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class SupplierProduct(Base, TimestampMixin):
    __tablename__ = "supplier_products"

    id: Mapped[int] = mapped_column(primary_key=True)

    supplier_id: Mapped[int] = mapped_column(
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    supplier_price: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2),
        nullable=True,
    )

    lead_time_days: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    is_preferred: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    supplier = relationship("Supplier", back_populates="products")

    product = relationship("Product", back_populates="suppliers")

    supplier_sku: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
