from __future__ import annotations

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    func,
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.models.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    # ----------------------------------
    # User
    # ----------------------------------

    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    user = relationship(
        "User",
    )

    # ----------------------------------
    # Action
    # ----------------------------------

    action: Mapped[str] = mapped_column(
        String(50),
        index=True,
        nullable=False,
    )

    entity_type: Mapped[str] = mapped_column(
        String(80),
        index=True,
        nullable=False,
    )

    entity_id: Mapped[int | None] = mapped_column(
        Integer,
        index=True,
        nullable=True,
    )

    summary: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    details: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # ----------------------------------
    # Actor Snapshot
    # ----------------------------------

    actor_name: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    department_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )

    department_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    location_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )

    location_name: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    role_names: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
    )

    # ----------------------------------
    # Request Information
    # ----------------------------------

    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
    )

    client_info: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # ----------------------------------
    # Document
    # ----------------------------------

    document_type: Mapped[str | None] = mapped_column(
        String(50),
        index=True,
        nullable=True,
    )

    document_number: Mapped[str | None] = mapped_column(
        String(50),
        index=True,
        nullable=True,
    )

    document_status: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    reference_document: Mapped[str | None] = mapped_column(
        String(50),
        index=True,
        nullable=True,
    )

    # ----------------------------------
    # Workflow
    # ----------------------------------

    workflow_id: Mapped[str | None] = mapped_column(
        String(100),
        index=True,
        nullable=True,
    )

    approval_level: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    approval_step: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # ----------------------------------
    # Data Snapshot
    # ----------------------------------

    before_data: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    after_data: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    # ----------------------------------
    # Origin
    # ----------------------------------

    source: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="USER",
        index=True,
    )

    # USER
    # SYSTEM
    # IMPORT


    import_batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("import_batches.id"),
        nullable=True,
        index=True,
    )


    extra_data: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )


    import_batch = relationship(
        "ImportBatch",
        back_populates="audit_logs",
    )