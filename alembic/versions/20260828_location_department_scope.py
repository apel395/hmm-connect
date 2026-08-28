"""Introduce Location -> Department organization mapping.

Revision ID: 20260828_location_department_scope
Revises: 20260828_beverage_syrup
"""

from alembic import op
import sqlalchemy as sa


revision = "20260828_location_department_scope"
down_revision = "20260828_beverage_syrup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "location_departments",
        sa.Column("location_id", sa.Integer(), nullable=False),
        sa.Column("department_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("location_id", "department_id", name="pk_location_departments"),
    )
    op.create_index("ix_location_departments_department_id", "location_departments", ["department_id"])

    # Preserve current behavior while making Location the operational pivot:
    # every active department is assigned to active locations in the same BU.
    # Shared departments (business_unit_id NULL) are made available to all
    # active locations. Future edits can narrow these mappings explicitly.
    op.execute(
        """
        INSERT INTO location_departments (location_id, department_id)
        SELECT l.id, d.id
        FROM locations l
        CROSS JOIN departments d
        WHERE l.is_active = true
          AND d.is_active = true
          AND (
              d.business_unit_id IS NULL
              OR d.business_unit_id = l.business_unit_id
          )
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index("ix_location_departments_department_id", table_name="location_departments")
    op.drop_table("location_departments")
