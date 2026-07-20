from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.models.base import Base
from app.models.user_role import UserRole
from app.models.role_permission import RolePermission


class Role(Base):

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False
    )

    description: Mapped[str | None] = mapped_column(
        String(200)
    )

    users = relationship(
        "User",
        secondary=UserRole.__table__,
        back_populates="roles"
    )

    permissions = relationship(
        "Permission",
        secondary=RolePermission.__table__,
        back_populates="roles"
    )