"""Backfill finance document locations from authoritative sources.

Revision ID: 20260827_finance_location_backfill
Revises: 20260827_inventory_uniqueness
"""

from alembic import op


revision = "20260827_finance_location_backfill"
down_revision = "20260827_inventory_uniqueness"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Warehouse receipts are anchored to the warehouse work location.
    op.execute(
        """
        UPDATE goods_receipts AS gr
        SET location_id = w.location_id
        FROM warehouses AS w
        WHERE gr.warehouse_id = w.id
          AND UPPER(COALESCE(gr.destination_type, '')) = 'WAREHOUSE'
          AND gr.location_id IS NULL
          AND w.location_id IS NOT NULL
        """
    )

    # PO-based non-warehouse receipts can inherit the PO location when missing.
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

    # Supplier invoices inherit receipt location first, then PO location.
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
        SET location_id = po.location_id
        FROM purchase_orders AS po
        WHERE si.purchase_order_id = po.id
          AND si.location_id IS NULL
          AND po.location_id IS NOT NULL
        """
    )

    # Repair already-generated finance journals from their supplier invoice.
    op.execute(
        """
        UPDATE journal_entries AS je
        SET
            location_id = si.location_id,
            business_unit_id = COALESCE(je.business_unit_id, si.business_unit_id),
            department_id = COALESCE(je.department_id, si.department_id)
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
        SET
            location_id = je.location_id,
            business_unit_id = COALESCE(jl.business_unit_id, je.business_unit_id),
            department_id = COALESCE(jl.department_id, je.department_id)
        FROM journal_entries AS je
        WHERE jl.journal_entry_id = je.id
          AND jl.location_id IS NULL
          AND je.location_id IS NOT NULL
        """
    )


def downgrade() -> None:
    # Backfilled organization dimensions represent repaired business data and
    # are intentionally not erased on downgrade.
    pass
