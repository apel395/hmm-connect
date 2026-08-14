"""Add Business Unit, Department, and Location master data.

Revision ID: 20260806_org_master_data
Revises: 20260805_financial_groups
"""
from alembic import op
import sqlalchemy as sa


revision = "20260806_org_master_data"
down_revision = "20260805_financial_groups"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "business_units",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("code", name="uq_business_units_code"),
        sa.UniqueConstraint("name", name="uq_business_units_name"),
    )
    op.create_index("ix_business_units_code", "business_units", ["code"])
    op.create_index("ix_business_units_is_active", "business_units", ["is_active"])

    op.add_column("departments", sa.Column("business_unit_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_departments_business_unit", "departments", "business_units", ["business_unit_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_departments_business_unit_id", "departments", ["business_unit_id"])
    op.create_index("ix_departments_code", "departments", ["code"])
    op.create_index("ix_departments_name", "departments", ["name"])

    # Nullable preserves existing rows; the create API requires this field for
    # all new locations.
    op.add_column("locations", sa.Column("business_unit_id", sa.Integer(), nullable=True))
    op.add_column("locations", sa.Column("address", sa.Text(), nullable=True))
    op.add_column("locations", sa.Column("city", sa.String(100), nullable=True))
    op.add_column("locations", sa.Column("province", sa.String(100), nullable=True))
    op.add_column("locations", sa.Column("postal_code", sa.String(20), nullable=True))
    op.create_foreign_key("fk_locations_business_unit", "locations", "business_units", ["business_unit_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_locations_business_unit_id", "locations", ["business_unit_id"])
    op.create_index("ix_locations_code", "locations", ["code"])
    op.create_index("ix_locations_name", "locations", ["name"])
    op.create_index("ix_locations_location_type", "locations", ["location_type"])

    op.execute("""
        INSERT INTO permissions (code, description)
        VALUES
          ('organization_dimensions.view', 'View Business Units, Departments, and Locations'),
          ('organization_dimensions.manage', 'Create and maintain Business Units, Departments, and Locations')
        ON CONFLICT (code) DO NOTHING
    """)
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r CROSS JOIN permissions p
        WHERE upper(r.name) IN ('ADMIN', 'ADMINISTRATOR', 'SUPER_ADMIN')
          AND p.code IN ('organization_dimensions.view', 'organization_dimensions.manage')
        ON CONFLICT DO NOTHING
    """)


def downgrade():
    op.execute("DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code IN ('organization_dimensions.view', 'organization_dimensions.manage'))")
    op.execute("DELETE FROM permissions WHERE code IN ('organization_dimensions.view', 'organization_dimensions.manage')")
    op.drop_index("ix_locations_location_type", table_name="locations")
    op.drop_index("ix_locations_name", table_name="locations")
    op.drop_index("ix_locations_code", table_name="locations")
    op.drop_index("ix_locations_business_unit_id", table_name="locations")
    op.drop_constraint("fk_locations_business_unit", "locations", type_="foreignkey")
    for column in ("postal_code", "province", "city", "address", "business_unit_id"):
        op.drop_column("locations", column)
    op.drop_index("ix_departments_name", table_name="departments")
    op.drop_index("ix_departments_code", table_name="departments")
    op.drop_index("ix_departments_business_unit_id", table_name="departments")
    op.drop_constraint("fk_departments_business_unit", "departments", type_="foreignkey")
    op.drop_column("departments", "business_unit_id")
    op.drop_index("ix_business_units_is_active", table_name="business_units")
    op.drop_index("ix_business_units_code", table_name="business_units")
    op.drop_table("business_units")
