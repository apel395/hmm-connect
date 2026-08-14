from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class ItemSubgroup(Base, TimestampMixin):
    __tablename__ = "item_subgroups"

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
    )

    group_id: Mapped[int] = mapped_column(
        ForeignKey("item_groups.id"),
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    group = relationship(
        "ItemGroup",
        back_populates="subgroups",
    )
