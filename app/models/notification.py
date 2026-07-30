# app/models/notification.py

from sqlalchemy import *
from app.core.database import Base

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)

    title = Column(String(255))
    message = Column(Text())

    reference_type = Column(String(50))
    reference_id = Column(Integer)

    is_read = Column(Boolean, default=False)

    created_at = Column(DateTime)
