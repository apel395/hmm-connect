from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class RecurringJournalLine(Base):

    __tablename__ = "recurring_journal_lines"

    id: Mapped[int] = mapped_column(primary_key=True)

    recurring_journal_id: Mapped[int] = mapped_column(
        ForeignKey("recurring_journals.id"),
    )

    account_id: Mapped[int] = mapped_column(
        ForeignKey("chart_of_accounts.id"),
    )

    debit: Mapped[float] = mapped_column(
        Numeric(18,2),
        default=0,
    )

    credit: Mapped[float] = mapped_column(
        Numeric(18,2),
        default=0,
    )

    description: Mapped[str | None] = mapped_column(
        String(255),
    )

    journal = relationship(
        "RecurringJournal",
        back_populates="lines",
    )

    account = relationship(
        "ChartOfAccount",
    )
