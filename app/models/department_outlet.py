"""An outlet is a selectable Hotel department linked to its parent department."""
from sqlalchemy import ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base

class DepartmentOutlet(Base):
    __tablename__='department_outlets'
    __table_args__=(CheckConstraint('department_id <> parent_department_id',name='ck_outlet_not_self'),)
    department_id: Mapped[int]=mapped_column(ForeignKey('departments.id',ondelete='CASCADE'),primary_key=True)
    parent_department_id: Mapped[int]=mapped_column(ForeignKey('departments.id',ondelete='RESTRICT'),nullable=False,index=True)
