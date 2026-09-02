from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class FiscalAccount(Base, TimestampMixin):
    __tablename__ = "fiscal_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    category: Mapped[str] = mapped_column(
        String(60), nullable=False, index=True
    )
    parent_code: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    is_header: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    mappings = relationship(
        "FiscalAccountMapping",
        back_populates="fiscal_account",
        cascade="all, delete-orphan",
    )


class FiscalAccountMapping(Base):
    __tablename__ = "fiscal_account_mappings"
    __table_args__ = (
        UniqueConstraint(
            "fiscal_account_id", "commercial_account_id", name="uq_fiscal_mapping_pair"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    fiscal_account_id: Mapped[int] = mapped_column(
        ForeignKey("fiscal_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    commercial_account_id: Mapped[int] = mapped_column(
        ForeignKey("chart_of_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    fiscal_account = relationship("FiscalAccount", back_populates="mappings")
    commercial_account = relationship("ChartOfAccount")