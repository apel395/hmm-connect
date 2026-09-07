"""Payment voucher (per location) before payment

Revision ID: 20260907_payment_vouchers
Revises: 20260904_opening_balances
"""

from alembic import op
import sqlalchemy as sa

revision = "20260907_payment_vouchers"
down_revision = "20260904_opening_balances"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_vouchers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("voucher_number", sa.String(length=50), nullable=False),
        sa.Column("voucher_date", sa.Date(), nullable=False),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("business_unit_id", sa.Integer(), sa.ForeignKey("business_units.id", ondelete="SET NULL"), nullable=True),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("period_from", sa.Date(), nullable=True),
        sa.Column("period_to", sa.Date(), nullable=True),
        sa.Column("total_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="DRAFT"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(length=30), nullable=False, server_default="LIVE"),
        sa.Column("external_reference", sa.String(length=100), nullable=True),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("voucher_number", name="uq_payment_vouchers_number"),
    )
    op.create_index("ix_payment_vouchers_location_id", "payment_vouchers", ["location_id"])
    op.create_index("ix_payment_vouchers_status", "payment_vouchers", ["status"])
    op.create_index("ix_payment_vouchers_payment_id", "payment_vouchers", ["payment_id"])

    op.create_table(
        "payment_voucher_allocations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("voucher_id", sa.Integer(), sa.ForeignKey("payment_vouchers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("supplier_invoice_id", sa.Integer(), sa.ForeignKey("supplier_invoices.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("allocated_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_payment_voucher_allocations_voucher_id", "payment_voucher_allocations", ["voucher_id"])
    op.create_index("ix_payment_voucher_allocations_invoice_id", "payment_voucher_allocations", ["supplier_invoice_id"])


def downgrade() -> None:
    op.drop_index("ix_payment_voucher_allocations_invoice_id", table_name="payment_voucher_allocations")
    op.drop_index("ix_payment_voucher_allocations_voucher_id", table_name="payment_voucher_allocations")
    op.drop_table("payment_voucher_allocations")
    op.drop_index("ix_payment_vouchers_payment_id", table_name="payment_vouchers")
    op.drop_index("ix_payment_vouchers_status", table_name="payment_vouchers")
    op.drop_index("ix_payment_vouchers_location_id", table_name="payment_vouchers")
    op.drop_table("payment_vouchers")
