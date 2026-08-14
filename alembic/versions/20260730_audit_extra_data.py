"""add missing audit log extra data

Revision ID: 20260730_audit_extra_data
Revises: 20260730_pr_expiry
Create Date: 2026-07-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260730_audit_extra_data"
down_revision: Union[str, Sequence[str], None] = "20260730_pr_expiry"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "audit_logs",
        sa.Column("extra_data", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("audit_logs", "extra_data")
