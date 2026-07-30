from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class JournalVoucher(Base):

    __tablename__ = "journal_vouchers"

    id: Mapped[int] = mapped_column(primary_key=True)

    voucher_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
    )

    voucher_date: Mapped[date] = mapped_column(Date)

    description: Mapped[str] = mapped_column(Text)

    status: Mapped[str] = mapped_column(
        String(20),
        default="POSTED",
    )

    created_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    created_by = relationship("User")

    lines = relationship(
        "JournalVoucherLine",
        cascade="all, delete-orphan",
    )
