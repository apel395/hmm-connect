from sqlalchemy import Boolean, String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Supplier(Base, TimestampMixin):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(150))
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    bank_account_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    bank_account_name: Mapped[str | None] = mapped_column(String(150), nullable=True)

    is_pkp: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    npwp: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    nitku: Mapped[str | None] = mapped_column(String(32), nullable=True)
    tax_registration_name: Mapped[str | None] = mapped_column(String(150), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    rows = relationship("SupplierRow", back_populates="supplier", cascade="all, delete-orphan", order_by="SupplierRow.id")
    purchase_orders = relationship("PurchaseOrder", back_populates="supplier")
    products = relationship("SupplierProduct", back_populates="supplier", cascade="all, delete-orphan")


class SupplierRow(Base):
    __tablename__ = "supplier_rows"

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False, index=True)
    pic_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(150), nullable=True)
    item: Mapped[str | None] = mapped_column(Text, nullable=True)
    supplier = relationship("Supplier", back_populates="rows")
