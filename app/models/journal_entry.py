from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text, func, Integer, event
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

    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_type: Mapped[str] = mapped_column(String(30), default="LIVE", nullable=False, index=True)
    external_reference: Mapped[str | None] = mapped_column(String(100))
    import_batch_id: Mapped[int | None] = mapped_column(ForeignKey("import_batches.id", ondelete="SET NULL"), nullable=True, index=True)
    imported_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    business_unit_id: Mapped[int | None] = mapped_column(ForeignKey("business_units.id", ondelete="SET NULL"), nullable=True, index=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id", ondelete="SET NULL"), nullable=True, index=True)

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


JOURNAL_ORIGIN_CODES = {
    "MANUAL": "MAN",
    "PERIOD_CLOSE": "CLOSE",
    "YEAR_END": "CLOSE",
    "SUPPLIER_INVOICE": "SI",
    "SUPPLIER_PAYMENT": "PAY",
    "SUPPLIER_ADJUSTMENT": "ADJ",
    "BANK_TRANSFER": "BTR",
    "FIXED_ASSET": "FA",
    "DEPRECIATION": "DEP",
    "AMORTIZATION": "AMO",
    "GOODS_RECEIPT": "GR",
    "CUSTOMER_PAYMENT": "CPAY",
    "SALES_TRANSACTION": "POS",
    "OPENING_BALANCE": "OPEN",
}


@event.listens_for(JournalEntry, "before_insert")
def apply_origin_journal_number(_mapper, _connection, target: JournalEntry):
    """Replace legacy JV prefixes with an origin code for new journal entries.

    The underlying JV sequence remains globally unique, while the visible number
    immediately identifies the originating accounting activity. Existing journal
    numbers and imported/external numbers are intentionally left unchanged.
    """
    number = target.journal_number or ""
    if not number.startswith("JV-"):
        return
    origin = JOURNAL_ORIGIN_CODES.get((target.reference_type or "").upper(), "MAN")
    target.journal_number = f"{origin}-{number[3:]}"
