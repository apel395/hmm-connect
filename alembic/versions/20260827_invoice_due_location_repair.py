"""Repair supplier invoice location and due date defaults.

Revision ID: 20260827_invoice_due_location_repair
Revises: 20260827_finance_concurrency_integrity
"""

from alembic import op


revision = "20260827_invoice_due_location_repair"
down_revision = "20260827_finance_concurrency_integrity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE supplier_invoices
        SET due_date = invoice_date + INTERVAL '30 days'
        WHERE due_date IS NULL
          AND invoice_date IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE supplier_invoices AS si
        SET location_id = COALESCE(
            gr.location_id,
            wh.location_id,
            po.location_id
        )
        FROM goods_receipts AS gr
        LEFT JOIN warehouses AS wh ON wh.id = gr.warehouse_id
        LEFT JOIN purchase_orders AS po ON po.id = COALESCE(si.purchase_order_id, gr.purchase_order_id)
        WHERE si.goods_receipt_id = gr.id
          AND si.location_id IS NULL
          AND COALESCE(gr.location_id, wh.location_id, po.location_id) IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE supplier_invoices AS si
        SET location_id = po.location_id
        FROM purchase_orders AS po
        WHERE si.purchase_order_id = po.id
          AND si.location_id IS NULL
          AND po.location_id IS NOT NULL
        """
    )


def downgrade() -> None:
    # Repaired business data is intentionally retained on downgrade.
    pass
