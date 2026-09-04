from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class OpeningBalance(Base, TimestampMixin):
    """Opening balance entry for a balance-sheet account at fiscal-year start.

    Entered once per fiscal year (not monthly). Flows through the journal/GL
    engine so it appears in the trial balance, balance sheet, and reports.
    """

    __tablename__ = "opening_balances"

    id: Mapped[int] = mapped_column(primary_key=True)

    fiscal_year: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("chart_of_accounts.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    location_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"))
    balance_type: Mapped[str] = mapped_column(String(10), default="DEBIT", nullable=False)
    description: Mapped[str | None] = mapped_column(String(250), nullable=True)

    journal_entry_id: Mapped[int | None] = mapped_column(
        ForeignKey("journal_entries.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    posted_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    posted_by = relationship("User", foreign_keys=[posted_by_id])
    journal_entry = relationship("JournalEntry")
    account = relationship("ChartOfAccount")
