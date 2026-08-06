from sqlalchemy import Boolean,String,Text
from sqlalchemy.orm import Mapped,mapped_column,relationship
from app.models.base import Base,TimestampMixin
class BusinessUnit(Base,TimestampMixin):
 __tablename__="business_units";id:Mapped[int]=mapped_column(primary_key=True);code:Mapped[str]=mapped_column(String(30),unique=True,index=True);name:Mapped[str]=mapped_column(String(100),unique=True);description:Mapped[str|None]=mapped_column(Text);is_active:Mapped[bool]=mapped_column(Boolean,default=True,index=True);locations=relationship("Location",back_populates="business_unit");departments=relationship("Department",back_populates="business_unit")
