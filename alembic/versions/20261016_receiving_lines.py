"""Persist receiving line destinations and explicit exception reasons.

Revision ID: 20261016_receiving_lines
Revises: 20261015_statistics
"""
from alembic import op
import sqlalchemy as sa

revision = "20261016_receiving_lines"
down_revision = "20261015_statistics"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("goods_receipt_items", sa.Column("destination_type", sa.String(30), nullable=True))
    op.add_column("goods_receipt_items", sa.Column("destination_override_reason", sa.String(500), nullable=True))
    # Existing rows deliberately remain NULL: the original receipt header is
    # their authoritative destination, not today's Item Master classification.


def downgrade():
    op.drop_column("goods_receipt_items", "destination_override_reason")
    op.drop_column("goods_receipt_items", "destination_type")
