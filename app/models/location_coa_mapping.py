from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ProductLocationCoaMapping(Base):
    __tablename__ = "product_location_coa_mappings"
    __table_args__ = (UniqueConstraint("product_id", "location_id", name="uq_product_location_coa"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True)
    inventory_account_id: Mapped[int | None] = mapped_column(ForeignKey("chart_of_accounts.id", ondelete="RESTRICT"))
    purchase_account_id: Mapped[int | None] = mapped_column(ForeignKey("chart_of_accounts.id", ondelete="RESTRICT"))
    cogs_account_id: Mapped[int | None] = mapped_column(ForeignKey("chart_of_accounts.id", ondelete="RESTRICT"))

    product = relationship("Product")
    location = relationship("Location")


class SupplierLocationCoaMapping(Base):
    __tablename__ = "supplier_location_coa_mappings"
    __table_args__ = (UniqueConstraint("supplier_id", "location_id", name="uq_supplier_location_coa"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False, index=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True)
    payable_account_id: Mapped[int] = mapped_column(ForeignKey("chart_of_accounts.id", ondelete="RESTRICT"), nullable=False)

    supplier = relationship("Supplier")
    location = relationship("Location")


class LocationTaxCoaMapping(Base):
    __tablename__ = "location_tax_coa_mappings"

    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    input_vat_account_id: Mapped[int] = mapped_column(ForeignKey("chart_of_accounts.id", ondelete="RESTRICT"), nullable=False)

    location = relationship("Location")
