from sqlalchemy import ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin


class ARInvoiceLayout(Base, TimestampMixin):
    __tablename__ = "ar_invoice_layouts"
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), primary_key=True)
    configuration: Mapped[dict] = mapped_column(JSON, nullable=False)
