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
    default_business_unit_id: Mapped[int | None] = mapped_column(ForeignKey("business_units.id", ondelete="SET NULL"), nullable=True, index=True)
    default_location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id", ondelete="SET NULL"), nullable=True, index=True)
    default_department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    default_business_unit = relationship("BusinessUnit", foreign_keys=[default_business_unit_id])
    default_location = relationship("Location", foreign_keys=[default_location_id])
    default_department = relationship("Department", foreign_keys=[default_department_id])

    department = relationship(
        "Department",
        back_populates="users", foreign_keys=[department_id],
    )

    location = relationship(
        "Location",
        back_populates="users", foreign_keys=[location_id],
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
