from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)

    payment_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
    )

    account_payable_id: Mapped[int] = mapped_column(
        ForeignKey("account_payables.id")
    )

    payment_date: Mapped[date] = mapped_column(Date)

    amount: Mapped[float] = mapped_column(
        Numeric(18, 2)
    )

    payment_method: Mapped[str] = mapped_column(
        String(50)
    )

    reference_number: Mapped[str | None] = mapped_column(
        String(100)
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="PAID",
    )

    created_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    account_payable = relationship("AccountPayable")
    created_by = relationship("User")