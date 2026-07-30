from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class PurchasingDocument(Base, TimestampMixin):
    __tablename__ = "purchasing_documents"
    __table_args__ = (
        CheckConstraint(
            "subtotal IS NULL OR subtotal >= 0",
            name="ck_purchasing_documents_subtotal_nonnegative",
        ),
        CheckConstraint(
            "tax_amount IS NULL OR tax_amount >= 0",
            name="ck_purchasing_documents_tax_nonnegative",
        ),
        CheckConstraint(
            "total_amount IS NULL OR total_amount >= 0",
            name="ck_purchasing_documents_total_nonnegative",
        ),
        Index(
            "ix_purchasing_documents_type_date",
            "document_type",
            "document_date",
        ),
        Index(
            "ix_purchasing_documents_stage_expected",
            "cashflow_stage",
            "expected_payment_date",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    document_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    document_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    supplier_id: Mapped[int | None] = mapped_column(
        ForeignKey("suppliers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    location_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    responsible_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    subtotal: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    tax_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    cashflow_stage: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    expected_payment_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        index=True,
    )
    external_reference: Mapped[str | None] = mapped_column(String(150), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
        index=True,
    )
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    supplier = relationship("Supplier")
    department = relationship("Department")
    location = relationship("Location")
    responsible_user = relationship(
        "User",
        foreign_keys=[responsible_user_id],
    )
    creator = relationship(
        "User",
        foreign_keys=[created_by],
    )
