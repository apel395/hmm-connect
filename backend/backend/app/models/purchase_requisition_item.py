from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PurchaseRequisitionItem(Base):
    __tablename__ = "purchase_requisition_items"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    purchase_requisition_id: Mapped[int] = mapped_column(
        ForeignKey(
            "purchase_requisitions.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id"),
        nullable=False,
    )

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    estimated_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    total_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    purchase_requisition = relationship(
        "PurchaseRequisition",
        back_populates="items",
    )

    product = relationship(
        "Product",
    )

    @property
    def product_code(self) -> str:
        return self.product.code

    @property
    def product_name(self) -> str:
        return self.product.name

    @property
    def product_uom(self) -> str:
        return self.product.uom