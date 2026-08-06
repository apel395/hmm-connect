from sqlalchemy import Boolean, String, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Location(Base, TimestampMixin):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    location_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        server_default="OFFICE",
    )
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    province: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    business_unit_id: Mapped[int | None] = mapped_column(ForeignKey("business_units.id", ondelete="RESTRICT"), nullable=True, index=True)
    business_unit = relationship("BusinessUnit", back_populates="locations")

    users = relationship("User", back_populates="location", foreign_keys="User.location_id")
