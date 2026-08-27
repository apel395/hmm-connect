from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Inventory(Base):
    __tablename__ = "inventory"
    __table_args__ = (
        UniqueConstraint("product_id", "warehouse_id", name="uq_inventory_product_warehouse"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouses.id", ondelete="CASCADE"),
        index=True,
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 4),
        default=Decimal("0"),
        nullable=False,
    )
    average_cost: Mapped[Decimal] = mapped_column(
        Numeric(14, 4),
        default=Decimal("0"),
        nullable=False,
    )

    product = relationship("Product", back_populates="inventory")
    warehouse = relationship("Warehouse")
