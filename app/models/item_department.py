"""Optional master ownership; does not allocate historical transactions."""
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class ItemDepartment(Base):
    __tablename__ = 'item_departments'
    product_id: Mapped[int] = mapped_column(ForeignKey('products.id'), primary_key=True)
    department_id: Mapped[int] = mapped_column(ForeignKey('departments.id'), index=True)
