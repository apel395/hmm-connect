"""add supplier tax profile and supplier invoice tax metadata

Revision ID: 20260814_supplier_tax_profile
Revises: 20260814_product_tax_profile
"""
from alembic import op
import sqlalchemy as sa

revision = "20260814_supplier_tax_profile"
down_revision = "20260814_product_tax_profile"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("suppliers", sa.Column("is_pkp", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("suppliers", sa.Column("npwp", sa.String(length=32), nullable=True))
    op.add_column("suppliers", sa.Column("nitku", sa.String(length=32), nullable=True))
    op.add_column("suppliers", sa.Column("tax_registration_name", sa.String(length=150), nullable=True))
    op.create_index("ix_suppliers_npwp", "suppliers", ["npwp"], unique=False)

    op.add_column("supplier_invoices", sa.Column("tax_invoice_number", sa.String(length=100), nullable=True))
    op.add_column("supplier_invoices", sa.Column("tax_invoice_date", sa.Date(), nullable=True))
    op.create_index("ix_supplier_invoices_tax_invoice_number", "supplier_invoices", ["tax_invoice_number"], unique=False)


def downgrade():
    op.drop_index("ix_supplier_invoices_tax_invoice_number", table_name="supplier_invoices")
    op.drop_column("supplier_invoices", "tax_invoice_date")
    op.drop_column("supplier_invoices", "tax_invoice_number")
    op.drop_index("ix_suppliers_npwp", table_name="suppliers")
    op.drop_column("suppliers", "tax_registration_name")
    op.drop_column("suppliers", "nitku")
    op.drop_column("suppliers", "npwp")
    op.drop_column("suppliers", "is_pkp")
