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
        SET location_id = gr.location_id
        FROM goods_receipts AS gr
        WHERE si.goods_receipt_id = gr.id
          AND si.location_id IS NULL
          AND gr.location_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE supplier_invoices AS si
        SET location_id = wh.location_id
        FROM goods_receipts AS gr, warehouses AS wh
        WHERE si.goods_receipt_id = gr.id
          AND gr.warehouse_id = wh.id
          AND si.location_id IS NULL
          AND wh.location_id IS NOT NULL
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
    op.execute(
        """
        UPDATE supplier_invoices AS si
        SET location_id = po.location_id
        FROM goods_receipts AS gr, purchase_orders AS po
        WHERE si.goods_receipt_id = gr.id
          AND gr.purchase_order_id = po.id
          AND si.location_id IS NULL
          AND po.location_id IS NOT NULL
        """
    )


def downgrade() -> None:
    # Repaired business data is intentionally retained on downgrade.
    pass
