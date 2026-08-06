"""Complete Budget lifecycle and organization-dimension constraints.

Revision ID: 20260809_budget_hardening
Revises: 20260808_org_dimensions
"""
from alembic import op
import sqlalchemy as sa

revision = "20260809_budget_hardening"
down_revision = "20260808_org_dimensions"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("budgets", sa.Column("submitted_at", sa.DateTime(timezone=True)))
    op.add_column("budgets", sa.Column("cancelled_at", sa.DateTime(timezone=True)))
    op.execute("""
        UPDATE budget_lines bl
        SET business_unit_id = l.business_unit_id
        FROM locations l
        WHERE bl.location_id = l.id AND bl.business_unit_id IS NULL
    """)
    op.execute("""
        UPDATE budget_lines bl
        SET business_unit_id = d.business_unit_id
        FROM departments d
        WHERE bl.department_id = d.id
          AND bl.business_unit_id IS NULL
          AND d.business_unit_id IS NOT NULL
    """)
    op.execute("""
        UPDATE budget_lines
        SET business_unit_id = (SELECT id FROM business_units WHERE code = 'HOTEL')
        WHERE business_unit_id IS NULL
    """)
    op.alter_column("budget_lines", "business_unit_id", existing_type=sa.Integer(), nullable=False)
    op.drop_constraint("uq_budget_line_dimensions", "budget_lines", type_="unique")
    op.create_unique_constraint(
        "uq_budget_line_dimension_ids", "budget_lines",
        ["budget_id", "month", "business_unit_id", "location_id", "department_id", "account_id"],
    )


def downgrade():
    op.drop_constraint("uq_budget_line_dimension_ids", "budget_lines", type_="unique")
    op.create_unique_constraint(
        "uq_budget_line_dimensions", "budget_lines",
        ["budget_id", "account_id", "department_id", "location_id", "month", "business_unit"],
    )
    op.alter_column("budget_lines", "business_unit_id", existing_type=sa.Integer(), nullable=True)
    op.drop_column("budgets", "cancelled_at")
    op.drop_column("budgets", "submitted_at")
