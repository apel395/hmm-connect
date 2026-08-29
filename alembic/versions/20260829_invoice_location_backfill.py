"""Backfill deterministic legacy Supplier Invoice locations.

Revision ID: 20260829_invoice_location_backfill
Revises: 20260828_location_department_scope
"""

from alembic import op


revision = "20260829_invoice_location_backfill"
down_revision = "20260828_location_department_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Resolve only unambiguous source chains. Conflicting receipt, warehouse,
    # and PO locations remain NULL so they can be reviewed instead of silently
    # rewriting the accounting dimension.
    op.execute(
        """
        WITH candidates AS (
            SELECT
                si.id,
                CASE
                    WHEN gr.id IS NOT NULL
                         AND UPPER(COALESCE(gr.destination_type, '')) = 'WAREHOUSE'
                         AND wh.location_id IS NOT NULL
                         AND (gr.location_id IS NULL OR gr.location_id = wh.location_id)
                         AND (po.location_id IS NULL OR po.location_id = wh.location_id)
                        THEN wh.location_id
                    WHEN gr.id IS NOT NULL
                         AND UPPER(COALESCE(gr.destination_type, '')) <> 'WAREHOUSE'
                         AND gr.location_id IS NOT NULL
                         AND (po.location_id IS NULL OR po.location_id = gr.location_id)
                        THEN gr.location_id
                    WHEN gr.id IS NOT NULL
                         AND UPPER(COALESCE(gr.destination_type, '')) <> 'WAREHOUSE'
                         AND gr.location_id IS NULL
                         AND wh.location_id IS NOT NULL
                         AND (po.location_id IS NULL OR po.location_id = wh.location_id)
                        THEN wh.location_id
                    WHEN gr.id IS NOT NULL
                         AND gr.location_id IS NULL
                         AND wh.location_id IS NULL
                         AND po.location_id IS NOT NULL
                        THEN po.location_id
                    WHEN gr.id IS NULL AND po.location_id IS NOT NULL
                        THEN po.location_id
                    ELSE NULL
                END AS location_id
            FROM supplier_invoices AS si
            LEFT JOIN goods_receipts AS gr ON gr.id = si.goods_receipt_id
            LEFT JOIN warehouses AS wh ON wh.id = gr.warehouse_id
            LEFT JOIN purchase_orders AS po
              ON po.id = COALESCE(si.purchase_order_id, gr.purchase_order_id)
            WHERE si.location_id IS NULL
        )
        UPDATE supplier_invoices AS si
        SET location_id = candidates.location_id
        FROM candidates
        WHERE si.id = candidates.id
          AND candidates.location_id IS NOT NULL
        """
    )


def downgrade() -> None:
    # Source-derived dimensions are business data. Reverting the migration must
    # not erase repaired invoice locations or modify historical journals.
    pass
