"""Enforce one inventory row per product and warehouse.

Revision ID: 20260827_inventory_uniqueness
Revises: 20260826_async_export_jobs
"""

from alembic import op


revision = "20260827_inventory_uniqueness"
down_revision = "20260826_async_export_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Consolidate any legacy duplicates before adding the unique constraint.
    op.execute(
        """
        WITH aggregated AS (
            SELECT
                product_id,
                warehouse_id,
                MIN(id) AS keep_id,
                SUM(quantity) AS total_quantity,
                CASE
                    WHEN SUM(quantity) = 0 THEN 0
                    ELSE SUM(quantity * average_cost) / SUM(quantity)
                END AS weighted_average_cost
            FROM inventory
            GROUP BY product_id, warehouse_id
            HAVING COUNT(*) > 1
        )
        UPDATE inventory AS target
        SET
            quantity = aggregated.total_quantity,
            average_cost = aggregated.weighted_average_cost
        FROM aggregated
        WHERE target.id = aggregated.keep_id
        """
    )
    op.execute(
        """
        WITH duplicates AS (
            SELECT
                product_id,
                warehouse_id,
                MIN(id) AS keep_id
            FROM inventory
            GROUP BY product_id, warehouse_id
            HAVING COUNT(*) > 1
        )
        DELETE FROM inventory AS target
        USING duplicates
        WHERE target.product_id = duplicates.product_id
          AND target.warehouse_id = duplicates.warehouse_id
          AND target.id <> duplicates.keep_id
        """
    )
    op.create_unique_constraint(
        "uq_inventory_product_warehouse",
        "inventory",
        ["product_id", "warehouse_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_inventory_product_warehouse",
        "inventory",
        type_="unique",
    )
