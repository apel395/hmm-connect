from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DocumentSequence(Base):
    __tablename__ = "document_sequences"

    sequence_key: Mapped[str] = mapped_column(String(40), primary_key=True)
    current_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
