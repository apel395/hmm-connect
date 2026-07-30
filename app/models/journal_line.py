from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class JournalLine(Base):
    __tablename__ = "journal_lines"

    id: Mapped[int] = mapped_column(primary_key=True)

    journal_entry_id: Mapped[int] = mapped_column(
        ForeignKey("journal_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    account_id: Mapped[int] = mapped_column(
        ForeignKey("chart_of_accounts.id"),
        nullable=False,
        index=True,
    )

    debit: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        default=0,
        nullable=False,
    )

    credit: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        default=0,
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    journal_entry = relationship(
        "JournalEntry",
        back_populates="lines",
    )

    account = relationship(
        "ChartOfAccount",
    )