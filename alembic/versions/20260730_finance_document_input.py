"""Add finance document input provenance and attachments.

Revision ID: 20260730_finance_documents
Revises: 20260730_audit_extra_data
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260730_finance_documents"
down_revision: str | None = "20260730_audit_extra_data"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("attachment_type", sa.String(length=50), nullable=False),
        sa.Column("document_number", sa.String(length=100), nullable=True),
        sa.Column("document_date", sa.Date(), nullable=True),
        sa.Column("original_file_name", sa.String(length=255), nullable=False),
        sa.Column("stored_file_name", sa.String(length=255), nullable=False),
        sa.Column(
            "storage_provider",
            sa.String(length=30),
            server_default="LOCAL",
            nullable=False,
        ),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "source_type",
            sa.String(length=30),
            server_default="LIVE",
            nullable=False,
        ),
        sa.Column("uploaded_by_id", sa.Integer(), nullable=True),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column("deleted_by_id", sa.Integer(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "source_type IN ('LIVE', 'HISTORICAL_IMPORT')",
            name="ck_document_attachments_source_type",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_id"],
            ["users.id"],
            name="fk_document_attachments_uploaded_by_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by_id"],
            ["users.id"],
            name="fk_document_attachments_deleted_by_id_users",
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_document_attachments_entity_type",
        "document_attachments",
        ["entity_type"],
    )
    op.create_index(
        "ix_document_attachments_entity_id",
        "document_attachments",
        ["entity_id"],
    )
    op.create_index(
        "ix_document_attachments_entity",
        "document_attachments",
        ["entity_type", "entity_id"],
    )

    for table_name in (
        "purchase_requisitions",
        "purchase_orders",
        "goods_receipts",
    ):
        op.add_column(
            table_name,
            sa.Column(
                "source_type",
                sa.String(length=30),
                server_default="LIVE",
                nullable=False,
            ),
        )
        op.add_column(
            table_name,
            sa.Column("external_reference", sa.String(length=100), nullable=True),
        )
        op.create_check_constraint(
            f"ck_{table_name}_source_type",
            table_name,
            "source_type IN ('LIVE', 'HISTORICAL_IMPORT')",
        )
        op.alter_column(table_name, "source_type", server_default=None)

    op.add_column(
        "goods_receipts",
        sa.Column(
            "receipt_type",
            sa.String(length=30),
            server_default="GOODS",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_goods_receipts_receipt_type",
        "goods_receipts",
        "receipt_type IN ('GOODS', 'SERVICE')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_goods_receipts_receipt_type", "goods_receipts", type_="check"
    )
    op.drop_column("goods_receipts", "receipt_type")

    for table_name in (
        "goods_receipts",
        "purchase_orders",
        "purchase_requisitions",
    ):
        op.drop_constraint(
            f"ck_{table_name}_source_type", table_name, type_="check"
        )
        op.drop_column(table_name, "external_reference")
        op.drop_column(table_name, "source_type")

    op.drop_index(
        "ix_document_attachments_entity", table_name="document_attachments"
    )
    op.drop_index(
        "ix_document_attachments_entity_id", table_name="document_attachments"
    )
    op.drop_index(
        "ix_document_attachments_entity_type", table_name="document_attachments"
    )
    op.drop_table("document_attachments")
