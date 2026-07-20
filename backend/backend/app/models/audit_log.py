from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    entity_type: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        index=True,
    )

    entity_id: Mapped[int | None] = mapped_column(
        nullable=True,
        index=True,
    )

    summary: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    details: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    actor_name: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    department_id: Mapped[int | None] = mapped_column(
        nullable=True,
        index=True,
    )

    department_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    location_id: Mapped[int | None] = mapped_column(
        nullable=True,
        index=True,
    )

    location_name: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    role_names: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    user = relationship("User")
