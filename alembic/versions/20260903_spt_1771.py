"""create company tax profile and tax credit tables for SPT 1771

Revision ID: 20260903_spt_1771
Revises: 20260902_fiscal_klasifikasi
"""

from alembic import op
import sqlalchemy as sa

revision = "20260903_spt_1771"
down_revision = "20260902_fiscal_klasifikasi"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "company_tax_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tax_year", sa.Integer(), nullable=False),
        sa.Column("npwp", sa.String(32), nullable=True),
        sa.Column("company_name", sa.String(250), nullable=True),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("klu", sa.String(20), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("email", sa.String(150), nullable=True),
        sa.Column("representative_name", sa.String(150), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_company_tax_profiles_tax_year", "company_tax_profiles", ["tax_year"], unique=True
    )

    op.create_table(
        "tax_credits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tax_year", sa.Integer(), nullable=False),
        sa.Column("credit_type", sa.String(20), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=True),
        sa.Column("description", sa.String(250), nullable=True),
        sa.Column("counterparty_npwp", sa.String(32), nullable=True),
        sa.Column("counterparty_name", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_tax_credits_tax_year", "tax_credits", ["tax_year"])
    op.create_index("ix_tax_credits_credit_type", "tax_credits", ["credit_type"])


def downgrade():
    op.drop_index("ix_tax_credits_credit_type", table_name="tax_credits")
    op.drop_index("ix_tax_credits_tax_year", table_name="tax_credits")
    op.drop_table("tax_credits")
    op.drop_index("ix_company_tax_profiles_tax_year", table_name="company_tax_profiles")
    op.drop_table("company_tax_profiles")
