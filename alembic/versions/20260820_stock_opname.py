"""add stock opname

Revision ID: 20260820_stock_opname
Revises: 20260820_approval_3lvl
"""

from alembic import op
import sqlalchemy as sa

revision = "20260820_stock_opname"
down_revision = "20260820_approval_3lvl"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "stock_opnames",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("opname_number", sa.String(50), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="DRAFT"),
        sa.Column("count_date", sa.Date(), nullable=False),
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
        sa.Column(
            "created_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("notes", sa.Text()),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("posted_at", sa.DateTime(timezone=True)),
        sa.Column(
            "posted_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")
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
        sa.UniqueConstraint("opname_number"),
    )
    for column in (
        "opname_number",
        "status",
        "warehouse_id",
        "business_unit_id",
        "location_id",
        "department_id",
        "created_by_id",
    ):
        op.create_index(f"ix_stock_opnames_{column}", "stock_opnames", [column])
    op.create_index(
        "uq_stock_opnames_active_warehouse",
        "stock_opnames",
        ["warehouse_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('DRAFT', 'PENDING_APPROVAL', 'APPROVED')"),
    )
    op.create_table(
        "stock_opname_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "stock_opname_id",
            sa.Integer(),
            sa.ForeignKey("stock_opnames.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            sa.Integer(),
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("system_quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("physical_quantity", sa.Numeric(14, 4)),
        sa.Column("variance_quantity", sa.Numeric(14, 4)),
        sa.Column("unit_cost", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("uom", sa.String(30), nullable=False),
        sa.UniqueConstraint(
            "stock_opname_id", "product_id", name="uq_stock_opname_product"
        ),
    )
    op.create_index(
        "ix_stock_opname_items_stock_opname_id",
        "stock_opname_items",
        ["stock_opname_id"],
    )
    op.create_index(
        "ix_stock_opname_items_product_id", "stock_opname_items", ["product_id"]
    )
    op.alter_column(
        "stock_movements",
        "quantity",
        existing_type=sa.Numeric(12, 2),
        type_=sa.Numeric(14, 4),
        existing_nullable=False,
    )

    bind = op.get_bind()
    workflow_id = bind.execute(
        sa.text("SELECT id FROM approval_workflows WHERE code='SO_APPROVAL'")
    ).scalar()
    if workflow_id is None:
        workflow_id = bind.execute(
            sa.text(
                "INSERT INTO approval_workflows (code,name,entity_type,is_active) VALUES ('SO_APPROVAL','Stock Opname Approval','STOCK_OPNAME',TRUE) RETURNING id"
            )
        ).scalar_one()
    role_rows = bind.execute(sa.text("SELECT id,name FROM roles")).fetchall()

    def norm(v):
        return "_".join(
            "".join(ch if ch.isalnum() else " " for ch in v.upper()).split()
        )

    roles = {norm(row.name): row.id for row in role_rows}
    steps = (
        (1, "Store Approval", "STORE"),
        (2, "Chef Approval", "CHEF"),
        (3, "PM / Camp Boss Approval", "PM/CAMP BOSS"),
    )
    missing = [name for _, _, name in steps if norm(name) not in roles]
    if missing:
        raise RuntimeError(
            "Required Stock Opname approval roles not found: " + ", ".join(missing)
        )
    bind.execute(
        sa.text("DELETE FROM approval_workflow_steps WHERE workflow_id=:id"),
        {"id": workflow_id},
    )
    for order, name, role in steps:
        bind.execute(
            sa.text(
                "INSERT INTO approval_workflow_steps (workflow_id,step_order,name,approver_role_id,department_id,location_id) VALUES (:w,:o,:n,:r,NULL,NULL)"
            ),
            {"w": workflow_id, "o": order, "n": name, "r": roles[norm(role)]},
        )


def downgrade():
    bind = op.get_bind()
    workflow_id = bind.execute(
        sa.text("SELECT id FROM approval_workflows WHERE code='SO_APPROVAL'")
    ).scalar()
    if workflow_id is not None:
        bind.execute(
            sa.text("DELETE FROM approval_workflow_steps WHERE workflow_id=:id"),
            {"id": workflow_id},
        )
        bind.execute(
            sa.text("DELETE FROM approval_workflows WHERE id=:id"), {"id": workflow_id}
        )
    op.alter_column(
        "stock_movements",
        "quantity",
        existing_type=sa.Numeric(14, 4),
        type_=sa.Numeric(12, 2),
        existing_nullable=False,
    )
    op.drop_table("stock_opname_items")
    op.drop_table("stock_opnames")
