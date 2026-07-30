from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.user_role import UserRole


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)

    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
    )

    email: Mapped[str] = mapped_column(
        String(120),
        unique=True,
    )

    full_name: Mapped[str] = mapped_column(
        String(150),
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
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

    department = relationship(
        "Department",
        back_populates="users",
    )

    location = relationship(
        "Location",
        back_populates="users",
    )

    roles = relationship(
        "Role",
        secondary=UserRole.__table__,
        back_populates="users",
    )

    # ---------------------------------------------------------
    # Journal
    # ---------------------------------------------------------

    created_journals = relationship(
        "JournalEntry",
        foreign_keys="JournalEntry.created_by_id",
        back_populates="created_by",
    )

    posted_journals = relationship(
        "JournalEntry",
        foreign_keys="JournalEntry.posted_by_id",
        back_populates="posted_by",
    )
