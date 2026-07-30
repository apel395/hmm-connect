from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class FiscalYearClose(Base, TimestampMixin):

    __tablename__ = "fiscal_year_close"

    id: Mapped[int] = mapped_column(primary_key=True)

    fiscal_year: Mapped[int] = mapped_column(
        Integer,
        unique=True,
        index=True,
    )

    closing_date: Mapped[date] = mapped_column(
        Date,
    )

    journal_entry_id: Mapped[int] = mapped_column(
        ForeignKey("journal_entries.id"),
    )

    is_closed: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    journal_entry = relationship(
        "JournalEntry",
    )
