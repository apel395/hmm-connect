from datetime import date, datetime

from decimal import Decimal
from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)

    payment_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
    )

    account_payable_id: Mapped[int | None] = mapped_column(
        ForeignKey("account_payables.id"), nullable=True
    )

    payment_date: Mapped[date] = mapped_column(Date)

    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2)
    )

    payment_method: Mapped[str] = mapped_column(
        String(50)
    )

    reference_number: Mapped[str | None] = mapped_column(
        String(100)
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="PAID",
    )

    created_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"), nullable=True, index=True)
    payment_account_id: Mapped[int | None] = mapped_column(ForeignKey("chart_of_accounts.id"), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="IDR", nullable=False)
    cheque_number: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(30), default="LIVE", nullable=False)
    approved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    posted_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    journal_entry_id: Mapped[int | None] = mapped_column(ForeignKey("journal_entries.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    account_payable = relationship("AccountPayable")
    created_by = relationship("User", foreign_keys=[created_by_id])
    supplier = relationship("Supplier")
    payment_account = relationship("ChartOfAccount")
    approved_by = relationship("User", foreign_keys=[approved_by_id])
    posted_by = relationship("User", foreign_keys=[posted_by_id])
    journal_entry = relationship("JournalEntry")
    allocations = relationship("PaymentAllocation", back_populates="payment", cascade="all, delete-orphan")


class PaymentAllocation(Base):
    __tablename__ = "payment_allocations"
    id: Mapped[int] = mapped_column(primary_key=True)
    payment_id: Mapped[int] = mapped_column(ForeignKey("payments.id", ondelete="CASCADE"), nullable=False, index=True)
    supplier_invoice_id: Mapped[int] = mapped_column(ForeignKey("supplier_invoices.id"), nullable=False, index=True)
    allocated_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    payment = relationship("Payment", back_populates="allocations")
    supplier_invoice = relationship("SupplierInvoice")
