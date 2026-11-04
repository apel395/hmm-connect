from sqlalchemy import ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin


class CateringLocationBilling(Base, TimestampMixin):
    __tablename__ = "catering_location_billing"
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"), primary_key=True)
    configuration: Mapped[dict] = mapped_column(JSON, nullable=False)
