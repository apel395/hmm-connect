from datetime import date

from sqlalchemy import Boolean, Date, Integer, String, JSON

from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class FiscalPeriod(Base, TimestampMixin):

    __tablename__ = "fiscal_periods"

    id: Mapped[int] = mapped_column(primary_key=True)

    fiscal_year: Mapped[int] = mapped_column(
        Integer,
        index=True,
    )

    fiscal_month: Mapped[int] = mapped_column(
        Integer,
        index=True,
    )

    period_name: Mapped[str] = mapped_column(
        String(20),
    )

    start_date: Mapped[date] = mapped_column(
        Date,
    )

    end_date: Mapped[date] = mapped_column(
        Date,
    )

    is_open: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    is_closed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    allow_backdated_entries: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False,
    )

    closing_journal_ids: Mapped[list[int]] = mapped_column(JSON, default=list, nullable=False, server_default="[]")

    closed_at: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
