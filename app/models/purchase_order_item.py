from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"

    id: Mapped[int] = mapped_column(primary_key=True)

    purchase_order_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_orders.id"),
        nullable=False,
    )

    purchase_requisition_item_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "purchase_requisition_items.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id"),
        nullable=False,
    )

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
    )

    received_quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=0,
    )

    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
    )

    total_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
    )

    purchase_order = relationship(
        "PurchaseOrder",
        back_populates="items",
    )

    purchase_requisition_item = relationship(
        "PurchaseRequisitionItem",
    )

    product = relationship(
        "Product",
    )

    goods_receipt_items = relationship(
        "GoodsReceiptItem",
        back_populates="purchase_order_item",
    )
