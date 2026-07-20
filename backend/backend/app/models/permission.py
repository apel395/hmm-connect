from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.models.base import Base
from app.models.role_permission import RolePermission


class Permission(Base):

    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(primary_key=True)

    code: Mapped[str] = mapped_column(
        String(100),
        unique=True
    )

    description: Mapped[str | None] = mapped_column(
        String(255)
    )

    roles = relationship(
        "Role",
        secondary=RolePermission.__table__,
        back_populates="permissions"
    )