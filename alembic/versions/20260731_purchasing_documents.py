"""create purchasing documents register

Revision ID: 20260731_purchasing_docs
Revises: 20260730_finance_documents
Create Date: 2026-07-31
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260731_purchasing_docs"
down_revision: str | None = "20260730_finance_documents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "purchasing_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_type", sa.String(length=50), nullable=False),
        sa.Column("document_number", sa.String(length=100), nullable=False),
        sa.Column("document_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("source_type", sa.String(length=30), nullable=False),
        sa.Column("supplier_id", sa.Integer(), nullable=True),
        sa.Column("department_id", sa.Integer(), nullable=True),
        sa.Column("location_id", sa.Integer(), nullable=True),
        sa.Column("responsible_user_id", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("subtotal", sa.Numeric(18, 2), nullable=True),
        sa.Column("tax_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("total_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("cashflow_stage", sa.String(length=30), nullable=False),
        sa.Column("expected_payment_date", sa.Date(), nullable=True),
        sa.Column("external_reference", sa.String(length=150), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "subtotal IS NULL OR subtotal >= 0",
            name="ck_purchasing_documents_subtotal_nonnegative",
        ),
        sa.CheckConstraint(
            "tax_amount IS NULL OR tax_amount >= 0",
            name="ck_purchasing_documents_tax_nonnegative",
        ),
        sa.CheckConstraint(
            "total_amount IS NULL OR total_amount >= 0",
            name="ck_purchasing_documents_total_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["department_id"],
            ["departments.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["locations.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["responsible_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            ondelete="SET NULL",
        ),
    )
    for column in (
        "document_type",
        "document_number",
        "document_date",
        "status",
        "source_type",
        "supplier_id",
        "department_id",
        "location_id",
        "cashflow_stage",
        "expected_payment_date",
        "is_active",
    ):
        op.create_index(
            f"ix_purchasing_documents_{column}",
            "purchasing_documents",
            [column],
        )
    op.create_index(
        "ix_purchasing_documents_type_date",
        "purchasing_documents",
        ["document_type", "document_date"],
    )
    op.create_index(
        "ix_purchasing_documents_stage_expected",
        "purchasing_documents",
        ["cashflow_stage", "expected_payment_date"],
    )


def downgrade() -> None:
    op.drop_table("purchasing_documents")
