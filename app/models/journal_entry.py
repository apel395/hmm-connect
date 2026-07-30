from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text, func, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class JournalEntry(Base, TimestampMixin):
    __tablename__ = "journal_entries"

    id: Mapped[int] = mapped_column(primary_key=True)

    journal_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    posting_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="POSTED",
        nullable=False,
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

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )

    posted_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )

    posted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    created_by = relationship(
        "User",
        foreign_keys=[created_by_id],
    )

    posted_by = relationship(
        "User",
        foreign_keys=[posted_by_id],
    )

    lines = relationship(
        "JournalLine",
        back_populates="journal_entry",
        cascade="all, delete-orphan",
    )

    fiscal_year: Mapped[int | None] = mapped_column(
        Integer,
        index=True,
    )

    fiscal_period: Mapped[int | None] = mapped_column(
        Integer,
        index=True,
    )