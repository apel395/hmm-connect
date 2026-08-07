"""Supplier credit and debit note adjustments.

Revision ID: 20260810_supplier_adjustments
Revises: 20260809_bank_payment_funding
"""
from alembic import op
import sqlalchemy as sa

revision = "20260810_supplier_adjustments"
down_revision = "20260809_bank_payment_funding"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("supplier_invoices", sa.Column("adjustment_amount", sa.Numeric(18, 2), nullable=False, server_default="0"))
    op.create_table(
        "supplier_adjustments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("adjustment_number", sa.String(50), nullable=False),
        sa.Column("adjustment_type", sa.String(20), nullable=False),
        sa.Column("supplier_invoice_id", sa.Integer(), sa.ForeignKey("supplier_invoices.id"), nullable=False),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("adjustment_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("adjustment_account_id", sa.Integer(), sa.ForeignKey("chart_of_accounts.id"), nullable=False),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
        sa.Column("business_unit_id", sa.Integer(), sa.ForeignKey("business_units.id", ondelete="SET NULL"), nullable=True),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("journal_entry_id", sa.Integer(), sa.ForeignKey("journal_entries.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("posted_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("adjustment_number", name="uq_supplier_adjustment_number"),
    )
    op.create_index("ix_supplier_adjustments_adjustment_number", "supplier_adjustments", ["adjustment_number"])
    op.create_index("ix_supplier_adjustments_adjustment_type", "supplier_adjustments", ["adjustment_type"])
    op.create_index("ix_supplier_adjustments_supplier_invoice_id", "supplier_adjustments", ["supplier_invoice_id"])
    op.create_index("ix_supplier_adjustments_supplier_id", "supplier_adjustments", ["supplier_id"])
    op.create_index("ix_supplier_adjustments_adjustment_date", "supplier_adjustments", ["adjustment_date"])
    op.create_index("ix_supplier_adjustments_status", "supplier_adjustments", ["status"])
    op.create_index("ix_supplier_adjustments_business_unit_id", "supplier_adjustments", ["business_unit_id"])
    op.create_index("ix_supplier_adjustments_location_id", "supplier_adjustments", ["location_id"])
    op.create_index("ix_supplier_adjustments_department_id", "supplier_adjustments", ["department_id"])


def downgrade():
    op.drop_index("ix_supplier_adjustments_department_id", table_name="supplier_adjustments")
    op.drop_index("ix_supplier_adjustments_location_id", table_name="supplier_adjustments")
    op.drop_index("ix_supplier_adjustments_business_unit_id", table_name="supplier_adjustments")
    op.drop_index("ix_supplier_adjustments_status", table_name="supplier_adjustments")
    op.drop_index("ix_supplier_adjustments_adjustment_date", table_name="supplier_adjustments")
    op.drop_index("ix_supplier_adjustments_supplier_id", table_name="supplier_adjustments")
    op.drop_index("ix_supplier_adjustments_supplier_invoice_id", table_name="supplier_adjustments")
    op.drop_index("ix_supplier_adjustments_adjustment_type", table_name="supplier_adjustments")
    op.drop_index("ix_supplier_adjustments_adjustment_number", table_name="supplier_adjustments")
    op.drop_table("supplier_adjustments")
    op.drop_column("supplier_invoices", "adjustment_amount")
