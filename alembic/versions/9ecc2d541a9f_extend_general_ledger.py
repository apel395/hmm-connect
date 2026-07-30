"""extend_general_ledger

Revision ID: 9ecc2d541a9f
Revises: 20260720_supplier_products
Create Date: 2026-07-22 12:05:07.624668
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9ecc2d541a9f"
down_revision: Union[str, Sequence[str], None] = "20260720_supplier_products"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "general_ledger",
        sa.Column("id", sa.Integer(), primary_key=True),

        sa.Column("journal_number", sa.String(50), nullable=False),

        sa.Column("posting_date", sa.Date(), nullable=False),

        sa.Column("fiscal_year", sa.Integer(), nullable=True),

        sa.Column("fiscal_period", sa.Integer(), nullable=True),

        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("chart_of_accounts.id"),
            nullable=False,
        ),

        sa.Column(
            "debit",
            sa.Numeric(18, 2),
            nullable=False,
            server_default="0",
        ),

        sa.Column(
            "credit",
            sa.Numeric(18, 2),
            nullable=False,
            server_default="0",
        ),

        sa.Column("journal_source", sa.String(50)),
        sa.Column("document_type", sa.String(50)),
        sa.Column("document_number", sa.String(100)),

        sa.Column("reference_type", sa.String(50), nullable=False),
        sa.Column("reference_id", sa.Integer(), nullable=False),
        sa.Column("reference_number", sa.String(100), nullable=False),

        sa.Column("description", sa.Text()),

        sa.Column(
            "created_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_general_ledger_journal_number",
        "general_ledger",
        ["journal_number"],
        unique=True,
    )

    op.create_index(
        "ix_general_ledger_posting_date",
        "general_ledger",
        ["posting_date"],
    )

    op.create_index(
        "ix_gl_fiscal_year",
        "general_ledger",
        ["fiscal_year"],
    )

    op.create_index(
        "ix_gl_fiscal_period",
        "general_ledger",
        ["fiscal_period"],
    )

    op.create_index(
        "ix_gl_journal_source",
        "general_ledger",
        ["journal_source"],
    )

    op.create_index(
        "ix_gl_document_type",
        "general_ledger",
        ["document_type"],
    )

    op.create_index(
        "ix_gl_document_number",
        "general_ledger",
        ["document_number"],
    )

    op.create_index(
        "ix_general_ledger_account_id",
        "general_ledger",
        ["account_id"],
    )

    op.create_index(
        "ix_general_ledger_reference_type",
        "general_ledger",
        ["reference_type"],
    )

    op.create_index(
        "ix_general_ledger_reference_id",
        "general_ledger",
        ["reference_id"],
    )

    op.create_index(
        "ix_general_ledger_reference_number",
        "general_ledger",
        ["reference_number"],
    )


def downgrade():
    op.drop_table("general_ledger")