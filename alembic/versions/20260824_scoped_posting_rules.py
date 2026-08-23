"""Scope accounting posting rules by business unit and location.

Revision ID: 20260824_scoped_posting_rules
Revises: 20260821_warehouse_location
"""

from alembic import op
import sqlalchemy as sa


revision = "20260824_scoped_posting_rules"
down_revision = "20260821_warehouse_location"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "accounting_posting_rules",
        sa.Column("business_unit_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "accounting_posting_rules",
        sa.Column("location_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_posting_rules_business_unit",
        "accounting_posting_rules",
        "business_units",
        ["business_unit_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_posting_rules_location",
        "accounting_posting_rules",
        "locations",
        ["location_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_accounting_posting_rules_business_unit_id",
        "accounting_posting_rules",
        ["business_unit_id"],
    )
    op.create_index(
        "ix_accounting_posting_rules_location_id",
        "accounting_posting_rules",
        ["location_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_accounting_posting_rules_location_id", table_name="accounting_posting_rules")
    op.drop_index("ix_accounting_posting_rules_business_unit_id", table_name="accounting_posting_rules")
    op.drop_constraint("fk_posting_rules_location", "accounting_posting_rules", type_="foreignkey")
    op.drop_constraint("fk_posting_rules_business_unit", "accounting_posting_rules", type_="foreignkey")
    op.drop_column("accounting_posting_rules", "location_id")
    op.drop_column("accounting_posting_rules", "business_unit_id")
