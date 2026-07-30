from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class AccountPayable(Base, TimestampMixin):
    __tablename__ = "account_payables"

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False)
    purchase_order_id: Mapped[int | None] = mapped_column(
        ForeignKey("purchase_orders.id", ondelete="SET NULL"),
        nullable=True,
    )
    invoice_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    invoice_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="OPEN", nullable=False)

    supplier = relationship("Supplier")
    purchase_order = relationship("PurchaseOrder")

    paid_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        default=0,
    )

    outstanding_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        default=0,
    )

    payment_status: Mapped[str] = mapped_column(
        String(30),
        default="UNPAID",
    )

    last_payment_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    matched: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    match_status: Mapped[str] = mapped_column(
        String(30),
        default="PENDING",
        nullable=False,
    )

    match_note: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
