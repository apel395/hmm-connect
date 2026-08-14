from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class AccountingSetting(Base):
    __tablename__ = "accounting_settings"

    id: Mapped[int] = mapped_column(primary_key=True)

    setting_key: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    account_id: Mapped[int] = mapped_column(
        ForeignKey("chart_of_accounts.id"),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        String(255),
    )

    account = relationship("ChartOfAccount")
