"""add transaction-safe document sequences

Revision ID: 20260801_document_sequences
Revises: 20260731_complete_coa
"""
from alembic import op
import sqlalchemy as sa

revision = "20260801_document_sequences"
down_revision = "20260731_complete_coa"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "document_sequences",
        sa.Column("sequence_key", sa.String(length=40), nullable=False),
        sa.Column("current_value", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("sequence_key"),
    )


def downgrade():
    op.drop_table("document_sequences")
