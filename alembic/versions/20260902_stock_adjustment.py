"""add stock adjustment

Revision ID: 20260902_stock_adjustment
Revises: 20260901_location2_accounting_settings
"""

from alembic import op
import sqlalchemy as sa

revision = "20260902_stock_adjustment"
down_revision = "20260901_location2_accounting_settings"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "stock_adjustments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("adjustment_number", sa.String(50), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="DRAFT"),
        sa.Column("adjustment_date", sa.Date(), nullable=False),
        sa.Column(
            "warehouse_id",
            sa.Integer(),
            sa.ForeignKey("warehouses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "business_unit_id",
            sa.Integer(),
            sa.ForeignKey("business_units.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "location_id",
            sa.Integer(),
            sa.ForeignKey("locations.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "department_id",
            sa.Integer(),
            sa.ForeignKey("departments.id", ondelete="RESTRICT"),
        ),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column(
            "created_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("posted_at", sa.DateTime(timezone=True)),
        sa.Column(
            "posted_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column(
            "total_adjustment_value",
            sa.Numeric(18, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("adjustment_number"),
    )
    for column in (
        "adjustment_number",
        "status",
        "warehouse_id",
        "business_unit_id",
        "location_id",
        "department_id",
        "created_by_id",
    ):
        op.create_index(f"ix_stock_adjustments_{column}", "stock_adjustments", [column])
    op.create_table(
        "stock_adjustment_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "stock_adjustment_id",
            sa.Integer(),
            sa.ForeignKey("stock_adjustments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            sa.Integer(),
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("system_quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("adjusted_quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("delta_quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("unit_cost", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("uom", sa.String(30), nullable=False),
        sa.Column("reason", sa.String(1000)),
        sa.Column("line_value", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.UniqueConstraint(
            "stock_adjustment_id", "product_id", name="uq_stock_adjustment_product"
        ),
    )
    op.create_index(
        "ix_stock_adjustment_items_stock_adjustment_id",
        "stock_adjustment_items",
        ["stock_adjustment_id"],
    )
    op.create_index(
        "ix_stock_adjustment_items_product_id", "stock_adjustment_items", ["product_id"]
    )

    op.execute(
        "INSERT INTO permissions (code, description) "
        "VALUES ('inventory.adjust', 'Adjust Warehouse Stock') "
        "ON CONFLICT (code) DO NOTHING"
    )
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT role.id, permission.id
        FROM roles AS role
        JOIN permissions AS permission ON permission.code = 'inventory.adjust'
        WHERE role.name IN ('WAREHOUSE', 'GENERAL_MANAGER', 'FINANCE', 'AUDITOR')
        ON CONFLICT DO NOTHING
        """
    )


def downgrade():
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN "
        "(SELECT id FROM permissions WHERE code = 'inventory.adjust')"
    )
    op.execute("DELETE FROM permissions WHERE code = 'inventory.adjust'")
    op.drop_table("stock_adjustment_items")
    op.drop_table("stock_adjustments")