"""Repair all resolvable Supplier Invoice locations.

Revision ID: 20260828_supplier_invoice_location_repair
Revises: 20260828_receiving_granular_permissions
"""

from alembic import op


revision = "20260828_supplier_invoice_location_repair"
down_revision = "20260828_receiving_granular_permissions"
branch_labels = None
depends_on = None


def upgrade() -> None:
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
        FROM goods_receipts AS gr
        JOIN warehouses AS wh ON wh.id = gr.warehouse_id
        WHERE si.goods_receipt_id = gr.id
          AND si.location_id IS NULL
          AND wh.location_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE supplier_invoices AS si
        SET location_id = po.location_id
        FROM goods_receipts AS gr
        JOIN purchase_orders AS po ON po.id = gr.purchase_order_id
        WHERE si.goods_receipt_id = gr.id
          AND si.location_id IS NULL
          AND po.location_id IS NOT NULL
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
    # Repaired source dimensions are business data and remain intact.
    pass
