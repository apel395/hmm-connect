from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Customer(Base, TimestampMixin):

    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)

    customer_code: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        index=True,
    )

    customer_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    email: Mapped[str | None] = mapped_column(
        String(150),
    )

    phone: Mapped[str | None] = mapped_column(
        String(50),
    )

    address: Mapped[str | None] = mapped_column(
        Text,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    account_receivables = relationship(
        "AccountReceivable",
        back_populates="customer",
    )
