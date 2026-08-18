"""add explicit market item flag and chef-first Market List approval

Revision ID: 20260818_market_item_flag
Revises: 20260816_market_list
"""
from alembic import op
import sqlalchemy as sa

revision = "20260818_market_item_flag"
down_revision = "20260816_market_list"
branch_labels = None
depends_on = None


ML_STEPS = (
    (1, "Chef Approval", "CHEF"),
    (2, "Store Approval", "STORE"),
    (3, "PM / Camp Boss Approval", "PM/CAMP BOSS"),
    (4, "Head Office Purchasing Approval", "HO PURCHASING"),
    (5, "Finance Approval", "FINANCE"),
    (6, "General Manager Approval", "GENERAL MANAGER"),
)


def upgrade():
    op.add_column(
        "products",
        sa.Column("is_market_item", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_products_is_market_item", "products", ["is_market_item"], unique=False)

    # Preserve the Market List population that was previously inferred from
    # FOOD/BEVERAGE, then make the classification explicit and editable.
    op.execute("UPDATE products SET is_market_item = TRUE WHERE group_code IN ('1', '2')")

    connection = op.get_bind()
    workflow_id = connection.execute(
        sa.text("SELECT id FROM approval_workflows WHERE code = 'ML_APPROVAL'")
    ).scalar()
    if workflow_id is None:
        workflow_id = connection.execute(
            sa.text(
                """
                INSERT INTO approval_workflows (code, name, entity_type, is_active)
                VALUES ('ML_APPROVAL', 'Market List Approval', 'MARKET_LIST', TRUE)
                RETURNING id
                """
            )
        ).scalar_one()
    else:
        connection.execute(
            sa.text(
                "UPDATE approval_workflows SET name='Market List Approval', entity_type='MARKET_LIST', is_active=TRUE WHERE id=:id"
            ),
            {"id": workflow_id},
        )

    role_ids = {}
    for _, _, role_name in ML_STEPS:
        role_id = connection.execute(
            sa.text("SELECT id FROM roles WHERE UPPER(TRIM(name)) = UPPER(:name) ORDER BY id LIMIT 1"),
            {"name": role_name},
        ).scalar()
        if role_id is None:
            raise RuntimeError(f"Required Market List approval role not found: {role_name}")
        role_ids[role_name] = role_id

    # Workflow configuration affects future submissions only. Existing approval
    # requests keep their immutable request-step snapshots.
    connection.execute(
        sa.text("DELETE FROM approval_workflow_steps WHERE workflow_id=:workflow_id"),
        {"workflow_id": workflow_id},
    )
    for step_order, name, role_name in ML_STEPS:
        connection.execute(
            sa.text(
                """
                INSERT INTO approval_workflow_steps
                    (workflow_id, step_order, name, approver_role_id)
                VALUES (:workflow_id, :step_order, :name, :role_id)
                """
            ),
            {
                "workflow_id": workflow_id,
                "step_order": step_order,
                "name": name,
                "role_id": role_ids[role_name],
            },
        )


def downgrade():
    connection = op.get_bind()
    workflow_id = connection.execute(
        sa.text("SELECT id FROM approval_workflows WHERE code = 'ML_APPROVAL'")
    ).scalar()
    if workflow_id is not None:
        # Restore the previous generated Market List order used by purchasing.
        previous_steps = (
            (1, "Store Approval", "STORE"),
            (2, "Chef Approval", "CHEF"),
            (3, "PM / Camp Boss Approval", "PM/CAMP BOSS"),
            (4, "Head Office Purchasing Approval", "HO PURCHASING"),
            (5, "Finance Approval", "FINANCE"),
            (6, "General Manager Approval", "GENERAL MANAGER"),
        )
        connection.execute(
            sa.text("DELETE FROM approval_workflow_steps WHERE workflow_id=:workflow_id"),
            {"workflow_id": workflow_id},
        )
        for step_order, name, role_name in previous_steps:
            role_id = connection.execute(
                sa.text("SELECT id FROM roles WHERE UPPER(TRIM(name)) = UPPER(:name) ORDER BY id LIMIT 1"),
                {"name": role_name},
            ).scalar()
            if role_id is not None:
                connection.execute(
                    sa.text(
                        """
                        INSERT INTO approval_workflow_steps
                            (workflow_id, step_order, name, approver_role_id)
                        VALUES (:workflow_id, :step_order, :name, :role_id)
                        """
                    ),
                    {
                        "workflow_id": workflow_id,
                        "step_order": step_order,
                        "name": name,
                        "role_id": role_id,
                    },
                )

    op.drop_index("ix_products_is_market_item", table_name="products")
    op.drop_column("products", "is_market_item")
