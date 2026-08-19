"""add store request and issue flow

Revision ID: 20260819_store_requests
Revises: 20260818_market_item_flag
"""
from alembic import op
import sqlalchemy as sa

revision = "20260819_store_requests"
down_revision = "20260818_market_item_flag"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "store_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sr_number", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="DRAFT"),
        sa.Column("request_date", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("business_unit_id", sa.Integer(), sa.ForeignKey("business_units.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("warehouse_id", sa.Integer(), sa.ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("requested_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("sr_number"),
    )
    for column in ("sr_number", "status", "business_unit_id", "department_id", "location_id", "warehouse_id", "requested_by_id"):
        op.create_index(f"ix_store_requests_{column}", "store_requests", [column], unique=False)

    op.create_table(
        "store_request_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("store_request_id", sa.Integer(), sa.ForeignKey("store_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("requested_quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("issued_quantity", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("uom", sa.String(length=30), nullable=False),
    )
    op.create_index("ix_store_request_items_store_request_id", "store_request_items", ["store_request_id"], unique=False)
    op.create_index("ix_store_request_items_product_id", "store_request_items", ["product_id"], unique=False)

    op.create_table(
        "store_issues",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("issue_number", sa.String(length=50), nullable=False),
        sa.Column("store_request_id", sa.Integer(), sa.ForeignKey("store_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="DRAFT"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("posted_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("issue_number"),
    )
    op.create_index("ix_store_issues_issue_number", "store_issues", ["issue_number"], unique=False)
    op.create_index("ix_store_issues_store_request_id", "store_issues", ["store_request_id"], unique=False)
    op.create_index("ix_store_issues_status", "store_issues", ["status"], unique=False)

    op.create_table(
        "store_issue_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("issue_id", sa.Integer(), sa.ForeignKey("store_issues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("store_request_item_id", sa.Integer(), sa.ForeignKey("store_request_items.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 4), nullable=False),
    )
    op.create_index("ix_store_issue_items_issue_id", "store_issue_items", ["issue_id"], unique=False)
    op.create_index("ix_store_issue_items_store_request_item_id", "store_issue_items", ["store_request_item_id"], unique=False)
    op.create_index("ix_store_issue_items_product_id", "store_issue_items", ["product_id"], unique=False)

    connection = op.get_bind()
    store_role_id = connection.execute(
        sa.text("SELECT id FROM roles WHERE UPPER(TRIM(name)) = 'STORE' ORDER BY id LIMIT 1")
    ).scalar()
    if store_role_id is None:
        raise RuntimeError("Required Store Request approval role not found: STORE")
    workflow_id = connection.execute(
        sa.text("SELECT id FROM approval_workflows WHERE code='SR_APPROVAL'")
    ).scalar()
    if workflow_id is None:
        workflow_id = connection.execute(
            sa.text(
                """
                INSERT INTO approval_workflows (code, name, entity_type, is_active)
                VALUES ('SR_APPROVAL', 'Store Request Approval', 'STORE_REQUEST', TRUE)
                RETURNING id
                """
            )
        ).scalar_one()
    else:
        connection.execute(
            sa.text("UPDATE approval_workflows SET name='Store Request Approval', entity_type='STORE_REQUEST', is_active=TRUE WHERE id=:id"),
            {"id": workflow_id},
        )
    existing_steps = connection.execute(
        sa.text("SELECT COUNT(*) FROM approval_workflow_steps WHERE workflow_id=:id"),
        {"id": workflow_id},
    ).scalar_one()
    if not existing_steps:
        connection.execute(
            sa.text(
                """
                INSERT INTO approval_workflow_steps (workflow_id, step_order, name, approver_role_id)
                VALUES (:workflow_id, 1, 'Store Approval', :role_id)
                """
            ),
            {"workflow_id": workflow_id, "role_id": store_role_id},
        )


def downgrade():
    connection = op.get_bind()
    workflow_id = connection.execute(sa.text("SELECT id FROM approval_workflows WHERE code='SR_APPROVAL'")).scalar()
    if workflow_id is not None:
        connection.execute(sa.text("DELETE FROM approval_workflow_steps WHERE workflow_id=:id"), {"id": workflow_id})
        connection.execute(sa.text("DELETE FROM approval_workflows WHERE id=:id"), {"id": workflow_id})
    op.drop_table("store_issue_items")
    op.drop_table("store_issues")
    op.drop_table("store_request_items")
    op.drop_table("store_requests")
