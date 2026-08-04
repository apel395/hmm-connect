from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class BankTransfer(Base):
    __tablename__ = "bank_transfers"
    id: Mapped[int] = mapped_column(primary_key=True)
    transfer_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    transfer_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    source_account_id: Mapped[int] = mapped_column(ForeignKey("chart_of_accounts.id"), nullable=False, index=True)
    destination_account_id: Mapped[int] = mapped_column(ForeignKey("chart_of_accounts.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="IDR", nullable=False)
    reference_number: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False, index=True)
    journal_entry_id: Mapped[int | None] = mapped_column(ForeignKey("journal_entries.id", ondelete="SET NULL"), unique=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    posted_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_account = relationship("ChartOfAccount", foreign_keys=[source_account_id])
    destination_account = relationship("ChartOfAccount", foreign_keys=[destination_account_id])
    journal_entry = relationship("JournalEntry")
    created_by = relationship("User", foreign_keys=[created_by_id])
    posted_by = relationship("User", foreign_keys=[posted_by_id])
