from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class PurchaseRequisition(Base, TimestampMixin):
    __tablename__ = "purchase_requisitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    pr_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", nullable=False)
    request_date: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), default="LIVE", nullable=False)
    external_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)

    items = relationship(
        "PurchaseRequisitionItem",
        back_populates="purchase_requisition",
        cascade="all, delete-orphan",
    )

    purchase_orders = relationship(
        "PurchaseOrder",
        secondary="purchase_order_requisitions",
        back_populates="purchase_requisitions",
    )

    legacy_purchase_orders = relationship(
        "PurchaseOrder",
        back_populates="purchase_requisition",
        foreign_keys="PurchaseOrder.purchase_requisition_id",
    )
