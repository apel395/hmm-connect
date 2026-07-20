"""add document traceability

Revision ID: 20260718_document_traceability
Revises: 20260718_audit_logs
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260718_document_traceability"
down_revision: Union[str, Sequence[str], None] = "20260718_audit_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "purchase_orders",
        sa.Column(
            "purchase_requisition_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_purchase_orders_purchase_requisition_id",
        "purchase_orders",
        ["purchase_requisition_id"],
    )

    op.create_foreign_key(
        "fk_purchase_orders_purchase_requisition_id",
        "purchase_orders",
        "purchase_requisitions",
        ["purchase_requisition_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "purchase_order_items",
        sa.Column(
            "purchase_requisition_item_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_purchase_order_items_purchase_requisition_item_id",
        "purchase_order_items",
        ["purchase_requisition_item_id"],
    )

    op.create_foreign_key(
        "fk_purchase_order_items_purchase_requisition_item_id",
        "purchase_order_items",
        "purchase_requisition_items",
        ["purchase_requisition_item_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.execute(
        sa.text(
            """
            UPDATE purchase_orders
            SET purchase_requisition_id = (
                SELECT pr.id
                FROM purchase_requisitions pr
                WHERE purchase_orders.notes LIKE
                      'Created from ' || pr.pr_number || '%'
                LIMIT 1
            )
            WHERE purchase_requisition_id IS NULL
            """
        )
    )

    op.execute(
        sa.text(
            """
            UPDATE purchase_order_items poi
            SET purchase_requisition_item_id = (
                SELECT pri.id
                FROM purchase_requisition_items pri
                WHERE pri.purchase_requisition_id =
                      po.purchase_requisition_id
                  AND pri.product_id = poi.product_id
                ORDER BY pri.id
                LIMIT 1
            )
            FROM purchase_orders po
            WHERE poi.purchase_order_id = po.id
              AND poi.purchase_requisition_item_id IS NULL
            """
        )
    )

    op.create_table(
        "goods_receipts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "receipt_number",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "purchase_order_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "received_by_id",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["purchase_order_id"],
            ["purchase_orders.id"],
        ),
        sa.ForeignKeyConstraint(
            ["received_by_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("receipt_number"),
    )

    op.create_index(
        "ix_goods_receipts_receipt_number",
        "goods_receipts",
        ["receipt_number"],
    )

    op.create_index(
        "ix_goods_receipts_purchase_order_id",
        "goods_receipts",
        ["purchase_order_id"],
    )

    op.create_table(
        "goods_receipt_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "goods_receipt_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "purchase_order_item_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "quantity",
            sa.Numeric(12, 2),
            nullable=False,
        ),
        sa.Column(
            "unit_cost",
            sa.Numeric(12, 2),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["goods_receipt_id"],
            ["goods_receipts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["purchase_order_item_id"],
            ["purchase_order_items.id"],
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
        ),
    )

    op.create_index(
        "ix_goods_receipt_items_goods_receipt_id",
        "goods_receipt_items",
        ["goods_receipt_id"],
    )

    op.add_column(
        "stock_movements",
        sa.Column(
            "goods_receipt_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_stock_movements_goods_receipt_id",
        "stock_movements",
        ["goods_receipt_id"],
    )

    op.create_foreign_key(
        "fk_stock_movements_goods_receipt_id",
        "stock_movements",
        "goods_receipts",
        ["goods_receipt_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.drop_constraint(
        "audit_logs_user_id_fkey",
        "audit_logs",
        type_="foreignkey",
    )

    op.create_foreign_key(
        "fk_audit_logs_user_id",
        "audit_logs",
        "users",
        ["user_id"],
        ["id"],
    )

    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION prevent_audit_log_mutation()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RAISE EXCEPTION
                    'audit_logs are immutable';
            END;
            $$;
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE TRIGGER audit_logs_immutable
            BEFORE UPDATE OR DELETE ON audit_logs
            FOR EACH ROW
            EXECUTE FUNCTION prevent_audit_log_mutation();
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS audit_logs_immutable ON audit_logs"
        )
    )

    op.execute(
        sa.text(
            "DROP FUNCTION IF EXISTS prevent_audit_log_mutation()"
        )
    )

    op.drop_constraint(
        "fk_audit_logs_user_id",
        "audit_logs",
        type_="foreignkey",
    )

    op.create_foreign_key(
        "audit_logs_user_id_fkey",
        "audit_logs",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.drop_constraint(
        "fk_stock_movements_goods_receipt_id",
        "stock_movements",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_stock_movements_goods_receipt_id",
        table_name="stock_movements",
    )
    op.drop_column("stock_movements", "goods_receipt_id")

    op.drop_index(
        "ix_goods_receipt_items_goods_receipt_id",
        table_name="goods_receipt_items",
    )
    op.drop_table("goods_receipt_items")

    op.drop_index(
        "ix_goods_receipts_purchase_order_id",
        table_name="goods_receipts",
    )
    op.drop_index(
        "ix_goods_receipts_receipt_number",
        table_name="goods_receipts",
    )
    op.drop_table("goods_receipts")

    op.drop_constraint(
        "fk_purchase_order_items_purchase_requisition_item_id",
        "purchase_order_items",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_purchase_order_items_purchase_requisition_item_id",
        table_name="purchase_order_items",
    )
    op.drop_column(
        "purchase_order_items",
        "purchase_requisition_item_id",
    )

    op.drop_constraint(
        "fk_purchase_orders_purchase_requisition_id",
        "purchase_orders",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_purchase_orders_purchase_requisition_id",
        table_name="purchase_orders",
    )
    op.drop_column(
        "purchase_orders",
        "purchase_requisition_id",
    )
