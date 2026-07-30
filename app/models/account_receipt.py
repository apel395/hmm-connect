from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class AccountReceipt(Base, TimestampMixin):
    __tablename__ = "account_receipts"

    id: Mapped[int] = mapped_column(primary_key=True)
    goods_receipt_id: Mapped[int] = mapped_column(
        ForeignKey("goods_receipts.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    account_id: Mapped[int] = mapped_column(ForeignKey("chart_of_accounts.id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    goods_receipt = relationship("GoodsReceipt")
    product = relationship("Product")
    account = relationship("ChartOfAccount", back_populates="account_receipts")
