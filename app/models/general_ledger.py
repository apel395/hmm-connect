from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class GeneralLedger(Base, TimestampMixin):
    __tablename__ = "general_ledger"

    id: Mapped[int] = mapped_column(primary_key=True)

    journal_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
    )

    posting_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    fiscal_year: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )

    fiscal_period: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
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

    journal_source: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )

    document_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )

    document_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    reference_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    reference_id: Mapped[int] = mapped_column(
        nullable=False,
        index=True,
    )

    reference_number: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )

    account = relationship(
        "ChartOfAccount",
        back_populates="general_ledger_entries",
    )

    created_by = relationship(
        "User",
    )