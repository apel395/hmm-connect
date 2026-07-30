from datetime import datetime

from sqlalchemy import String, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class RefreshToken(Base):

    __tablename__ = "refresh_tokens"


    id: Mapped[int] = mapped_column(
        primary_key=True
    )


    token: Mapped[str] = mapped_column(
        String(500),
        unique=True,
        nullable=False
    )


    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id")
    )


    expires_at: Mapped[datetime] = mapped_column(
        DateTime
    )


    user = relationship(
        "User"
    )