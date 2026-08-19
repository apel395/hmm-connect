"""add single-session tracking and normalize market-list classification

Revision ID: 20260819_market_session
Revises: 20260819_store_requests
Create Date: 2026-08-19
"""

from alembic import op
import sqlalchemy as sa


revision = "20260819_market_session"
down_revision = "20260819_store_requests"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("active_session_id", sa.String(length=36), nullable=True))
    op.add_column("users", sa.Column("session_last_activity_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_users_active_session_id", "users", ["active_session_id"], unique=False)

    # Market List is now derived only from canonical Product subgroup.
    op.execute(
        """
        UPDATE products
        SET is_market_item = CASE
            WHEN UPPER(TRIM(COALESCE(subgroup_name, ''))) IN ('VEGETABLES', 'FRUIT') THEN TRUE
            ELSE FALSE
        END
        """
    )


def downgrade():
    op.drop_index("ix_users_active_session_id", table_name="users")
    op.drop_column("users", "session_last_activity_at")
    op.drop_column("users", "active_session_id")
