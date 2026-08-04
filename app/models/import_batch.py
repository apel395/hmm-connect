from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
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
        nullable=True,
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


    audit_logs = relationship(
        "AuditLog",
        back_populates="import_batch",
    )

    batch_name: Mapped[str] = mapped_column(String(150), nullable=False)
    import_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    import_mode: Mapped[str] = mapped_column(String(20), default="STRICT", nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), default="HISTORICAL_IMPORT", nullable=False)
    period_from: Mapped[Date | None] = mapped_column(Date, index=True)
    period_to: Mapped[Date | None] = mapped_column(Date, index=True)
    file_name: Mapped[str | None] = mapped_column(String(255))
    original_file_name: Mapped[str | None] = mapped_column(String(255))
    stored_file_path: Mapped[str | None] = mapped_column(String(500))
    total_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    valid_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    warning_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    imported_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    validated_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

    created_by = relationship("User", foreign_keys=[created_by_id])
    rows = relationship("ImportRow", back_populates="batch", cascade="all, delete-orphan")


class ImportRow(Base):
    __tablename__ = "import_rows"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    import_batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    sheet_name: Mapped[str | None] = mapped_column(String(100))
    document_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    raw_data_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    normalized_data_json: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(50), index=True)
    entity_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    document_number: Mapped[str | None] = mapped_column(String(100), index=True)
    warning_messages_json: Mapped[list | None] = mapped_column(JSON)
    error_messages_json: Mapped[list | None] = mapped_column(JSON)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    imported_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    batch = relationship("ImportBatch", back_populates="rows")
