from sqlalchemy import Boolean, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Department(Base, TimestampMixin):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(primary_key=True)

    code: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        index=True,
        nullable=False
    )

    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )
    business_unit_id: Mapped[int | None] = mapped_column(ForeignKey("business_units.id", ondelete="SET NULL"), nullable=True, index=True)
    business_unit = relationship("BusinessUnit", back_populates="departments")

    users = relationship(
        "User",
        back_populates="department",
        foreign_keys="User.department_id",
    )
