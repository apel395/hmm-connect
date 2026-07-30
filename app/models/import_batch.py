from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.models.base import Base


class ImportBatch(Base):

    __tablename__ = "import_batches"


    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )


    batch_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )


    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    # ACCOUNTING_IMPORT
    # MIGRATION
    # LEGACY_SYSTEM


    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )


    imported_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )


    imported_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


    total_documents: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )


    success_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )


    failed_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )


    status: Mapped[str] = mapped_column(
        String(30),
        default="PROCESSING",
        nullable=False,
    )

    # PROCESSING
    # COMPLETED
    # FAILED


    activities = relationship(
        "AuditLog",
        back_populates="import_batch",
    )