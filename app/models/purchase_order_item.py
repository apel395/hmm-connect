from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_order_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"), nullable=False)
    purchase_requisition_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("purchase_requisition_items.id", ondelete="SET NULL"), nullable=True, index=True
    )
    market_list_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("market_list_items.id", ondelete="SET NULL"), nullable=True, index=True
    )
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    uom: Mapped[str | None] = mapped_column(String(20), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    received_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    total_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    is_taxable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)

    purchase_order = relationship("PurchaseOrder", back_populates="items")
    purchase_requisition_item = relationship("PurchaseRequisitionItem")
    market_list_item = relationship("MarketListItem")
    product = relationship("Product")
    goods_receipt_items = relationship("GoodsReceiptItem", back_populates="purchase_order_item")
