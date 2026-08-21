from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Warehouse(Base, TimestampMixin):
    __tablename__ = "warehouses"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    location_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    location = relationship("Location")
