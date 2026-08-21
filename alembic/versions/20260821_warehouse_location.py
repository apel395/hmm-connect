"""map warehouses to work locations

Revision ID: 20260821_warehouse_location
Revises: 20260820_stock_opname
"""

from alembic import op
import sqlalchemy as sa


revision = "20260821_warehouse_location"
down_revision = "20260820_stock_opname"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "warehouses",
        sa.Column(
            "location_id",
            sa.Integer(),
            sa.ForeignKey("locations.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_warehouses_location_id",
        "warehouses",
        ["location_id"],
    )

    # Preserve single-location installations without manual intervention.
    # Multi-location installations intentionally leave legacy warehouses
    # unmapped so an administrator can assign the correct work location.
    bind = op.get_bind()
    active_locations = bind.execute(
        sa.text("SELECT id FROM locations WHERE is_active = TRUE ORDER BY id")
    ).scalars().all()
    if len(active_locations) == 1:
        bind.execute(
            sa.text(
                "UPDATE warehouses SET location_id = :location_id "
                "WHERE location_id IS NULL"
            ),
            {"location_id": active_locations[0]},
        )


def downgrade():
    op.drop_index("ix_warehouses_location_id", table_name="warehouses")
    op.drop_column("warehouses", "location_id")
