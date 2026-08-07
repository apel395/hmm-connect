from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class BankAccount(Base):
    __tablename__ = "bank_accounts"
    __table_args__ = (
        UniqueConstraint("bank_name", "account_number", name="uq_bank_account_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    bank_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    account_name: Mapped[str] = mapped_column(String(180), nullable=False)
    account_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    account_holder: Mapped[str | None] = mapped_column(String(180), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="IDR", nullable=False)
    business_unit_id: Mapped[int] = mapped_column(ForeignKey("business_units.id"), nullable=False, index=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"), nullable=True, index=True)
    coa_account_id: Mapped[int] = mapped_column(ForeignKey("chart_of_accounts.id"), nullable=False, unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    business_unit = relationship("BusinessUnit")
    location = relationship("Location")
    coa_account = relationship("ChartOfAccount")
