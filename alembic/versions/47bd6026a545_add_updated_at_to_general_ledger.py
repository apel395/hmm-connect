"""add_updated_at_to_general_ledger

Revision ID: 47bd6026a545
Create Date: 2026-07-23 13:09:38.695814

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision = "47bd6026a545"
down_revision = "b43067e8ad3e"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column(
        "general_ledger",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column(
        "general_ledger",
        "updated_at",
    )
