"""Add params column to async export jobs.

Revision ID: 20260917_export_job_params
Revises: 20260915_pos_table_invoice
"""

from alembic import op
import sqlalchemy as sa


revision = "20260917_export_job_params"
down_revision = "20260915_pos_table_invoice"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("export_jobs", sa.Column("params", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("export_jobs", "params")