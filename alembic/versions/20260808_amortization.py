"""Add amortization records.

Revision ID: 20260808_amortization
Revises: 20260807_direct_receiving
"""
from alembic import op

from app.models.amortization import Amortization


revision = "20260808_amortization"
down_revision = "20260807_direct_receiving"
branch_labels = None
depends_on = None


def upgrade():
    Amortization.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    Amortization.__table__.drop(op.get_bind(), checkfirst=True)
