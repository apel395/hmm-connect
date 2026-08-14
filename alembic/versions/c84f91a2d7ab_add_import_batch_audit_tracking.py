"""add import batch audit tracking

Revision ID: c84f91a2d7ab
Revises: 47bd6026a545
Create Date: 2026-07-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c84f91a2d7ab"

down_revision: Union[str, Sequence[str], None] = "47bd6026a545"

branch_labels: Union[str, Sequence[str], None] = None

depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    # ----------------------------------
    # Import Batch
    # ----------------------------------

    op.create_table(
        "import_batches",

        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
        ),

        sa.Column(
            "batch_number",
            sa.String(50),
            nullable=False,
            unique=True,
        ),

        sa.Column(
            "source",
            sa.String(50),
            nullable=False,
        ),

        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
        ),

        sa.Column(
            "imported_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),

        sa.Column(
            "imported_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),

        sa.Column(
            "total_documents",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),

        sa.Column(
            "success_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),

        sa.Column(
            "failed_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),

        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default="PROCESSING",
        ),
    )


    op.create_index(
        "ix_import_batches_batch_number",
        "import_batches",
        ["batch_number"],
        unique=True,
    )


    op.create_index(
        "ix_import_batches_source",
        "import_batches",
        ["source"],
    )


    # ----------------------------------
    # Extend audit logs
    # ----------------------------------

    op.add_column(
        "audit_logs",
        sa.Column(
            "source",
            sa.String(30),
            nullable=False,
            server_default="USER",
        ),
    )


    op.add_column(
        "audit_logs",
        sa.Column(
            "import_batch_id",
            sa.BigInteger(),
            sa.ForeignKey("import_batches.id"),
            nullable=True,
        ),
    )


    op.add_column(
        "audit_logs",
        sa.Column(
            "metadata",
            sa.JSON(),
            nullable=True,
        ),
    )


    op.create_index(
        "ix_audit_logs_source",
        "audit_logs",
        ["source"],
    )


    op.create_index(
        "ix_audit_logs_import_batch_id",
        "audit_logs",
        ["import_batch_id"],
    )


def downgrade() -> None:

    op.drop_index(
        "ix_audit_logs_import_batch_id",
        table_name="audit_logs",
    )

    op.drop_index(
        "ix_audit_logs_source",
        table_name="audit_logs",
    )

    op.drop_column(
        "audit_logs",
        "metadata",
    )

    op.drop_column(
        "audit_logs",
        "import_batch_id",
    )

    op.drop_column(
        "audit_logs",
        "source",
    )


    op.drop_index(
        "ix_import_batches_source",
        table_name="import_batches",
    )

    op.drop_index(
        "ix_import_batches_batch_number",
        table_name="import_batches",
    )

    op.drop_table(
        "import_batches",
    )
