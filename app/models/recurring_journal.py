from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class RecurringJournal(Base, TimestampMixin):

    __tablename__ = "recurring_journals"

    id: Mapped[int] = mapped_column(primary_key=True)

    journal_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    frequency: Mapped[str] = mapped_column(
        String(20),
        default="MONTHLY",
    )

    next_run_day: Mapped[int] = mapped_column(
        Integer,
        default=1,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    created_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
    )

    created_by = relationship("User")

    lines = relationship(
        "RecurringJournalLine",
        back_populates="journal",
        cascade="all, delete-orphan",
    )
