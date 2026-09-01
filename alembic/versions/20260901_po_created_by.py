"""Add created_by_id to purchase_orders for transaction traceability.

Records who created each purchase order, mirroring the attribution columns
already present on other transaction documents (GR received_by_id, Stock
Opname created_by_id, Supplier Invoice created_by_id, Payment created_by_id,
Market List / Store Request requested_by_id). Backfills existing purchase
orders from the CREATE audit log entry so every transaction is traceable.

Revision ID: 20260901_po_created_by
Revises: 20260829_invoice_location_backfill
"""
from alembic import op
import sqlalchemy as sa

revision = "20260901_po_created_by"
down_revision = "20260829_invoice_location_backfill"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "purchase_orders",
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_purchase_orders_created_by_id", "purchase_orders", ["created_by_id"])

    # Backfill the creator for existing purchase orders from the audit trail.
    # The PO create flow logs entity_type='PURCHASE_ORDER', action='CREATE',
    # actor stored as user_id, source='USER'.
    op.execute(
        """
        UPDATE purchase_orders po
        SET created_by_id = al.user_id
        FROM (
            SELECT DISTINCT ON (entity_id)
                entity_id,
                user_id
            FROM audit_logs
            WHERE entity_type = 'PURCHASE_ORDER'
              AND action = 'CREATE'
              AND source = 'USER'
              AND user_id IS NOT NULL
            ORDER BY entity_id, created_at ASC
        ) al
        WHERE po.id = al.entity_id
          AND po.created_by_id IS NULL
        """
    )


def downgrade():
    op.drop_index("ix_purchase_orders_created_by_id", table_name="purchase_orders")
    op.drop_column("purchase_orders", "created_by_id")
