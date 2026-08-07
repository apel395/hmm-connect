from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class SupplierAdjustment(Base):
    __tablename__ = "supplier_adjustments"

    id: Mapped[int] = mapped_column(primary_key=True)
    adjustment_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    adjustment_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    supplier_invoice_id: Mapped[int] = mapped_column(ForeignKey("supplier_invoices.id"), nullable=False, index=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False, index=True)
    adjustment_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    adjustment_account_id: Mapped[int] = mapped_column(ForeignKey("chart_of_accounts.id"), nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False, index=True)
    business_unit_id: Mapped[int | None] = mapped_column(ForeignKey("business_units.id", ondelete="SET NULL"), index=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id", ondelete="SET NULL"), index=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"), index=True)
    journal_entry_id: Mapped[int | None] = mapped_column(ForeignKey("journal_entries.id", ondelete="SET NULL"))
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    posted_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    supplier_invoice = relationship("SupplierInvoice")
    supplier = relationship("Supplier")
    adjustment_account = relationship("ChartOfAccount", foreign_keys=[adjustment_account_id])
    journal_entry = relationship("JournalEntry")
    created_by = relationship("User", foreign_keys=[created_by_id])
    posted_by = relationship("User", foreign_keys=[posted_by_id])
