"""Add async journal import worker fields to import batches.

Revision ID: 20260921_async_journal_import
Revises: 20260917_export_job_params
"""

from alembic import op
import sqlalchemy as sa


revision = "20260921_async_journal_import"
down_revision = "20260917_export_job_params"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "import_batches",
        sa.Column("worker_command_id", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "import_batches",
        sa.Column("worker_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "import_batches",
        sa.Column("worker_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "import_batches",
        sa.Column("worker_error_message", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("import_batches", "worker_error_message")
    op.drop_column("import_batches", "worker_completed_at")
    op.drop_column("import_batches", "worker_started_at")
    op.drop_column("import_batches", "worker_command_id")
