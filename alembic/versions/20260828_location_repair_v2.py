"""Persist source-resolved finance locations after direct COA rollout.

Revision ID: 20260828_location_repair_v2
Revises: 20260828_direct_coa_mapping
"""

from alembic import op


revision = "20260828_location_repair_v2"
down_revision = "20260828_direct_coa_mapping"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Repair source documents first so every downstream update reads a stable value.
    op.execute(
        """
        UPDATE goods_receipts AS gr
        SET location_id = wh.location_id
        FROM warehouses AS wh
        WHERE gr.warehouse_id = wh.id
          AND gr.location_id IS NULL
          AND wh.location_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE goods_receipts AS gr
        SET location_id = po.location_id
        FROM purchase_orders AS po
        WHERE gr.purchase_order_id = po.id
          AND gr.location_id IS NULL
          AND po.location_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE supplier_invoices AS si
        SET location_id = COALESCE(gr.location_id, wh.location_id, po.location_id)
        FROM goods_receipts AS gr
        LEFT JOIN warehouses AS wh ON wh.id = gr.warehouse_id
        LEFT JOIN purchase_orders AS po ON po.id = gr.purchase_order_id
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

    # Keep already-created finance snapshots aligned, without touching rows that
    # already carry an explicit location.
    op.execute(
        """
        UPDATE journal_entries AS je
        SET location_id = si.location_id
        FROM supplier_invoices AS si
        WHERE je.reference_type = 'SUPPLIER_INVOICE'
          AND je.reference_id = si.id
          AND je.location_id IS NULL
          AND si.location_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE journal_lines AS jl
        SET location_id = je.location_id
        FROM journal_entries AS je
        WHERE jl.journal_entry_id = je.id
          AND jl.location_id IS NULL
          AND je.location_id IS NOT NULL
        """
    )


def downgrade() -> None:
    # Repaired business dimensions are intentionally retained.
    pass
