from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class ItemGroup(Base, TimestampMixin):
    __tablename__ = "item_groups"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    code: Mapped[str] = mapped_column(
        String(10),
        unique=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        index=True,
    )

    item_type: Mapped[str] = mapped_column(
        String(4),
        default="BUY",
        nullable=False,
        index=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    subgroups = relationship(
        "ItemSubgroup",
        back_populates="group",
        cascade="all, delete-orphan",
    )
