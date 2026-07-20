"""procurement accounting and warehouse controls

Revision ID: 20260720_procurement_accounting
Revises: 20260718_document_traceability
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260720_procurement_accounting"
down_revision: Union[str, Sequence[str], None] = "20260718_document_traceability"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "departments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("code", name="uq_departments_code"),
        sa.UniqueConstraint("name", name="uq_departments_name"),
    )

    op.add_column(
        "users",
        sa.Column("department_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_users_department_id", "users", ["department_id"])
    op.create_foreign_key(
        "fk_users_department_id",
        "users",
        "departments",
        ["department_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "purchase_order_requisitions",
        sa.Column("purchase_order_id", sa.Integer(), nullable=False),
        sa.Column("purchase_requisition_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["purchase_order_id"],
            ["purchase_orders.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["purchase_requisition_id"],
            ["purchase_requisitions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "purchase_order_id",
            "purchase_requisition_id",
        ),
    )

    op.execute(
        sa.text(
            """
            INSERT INTO purchase_order_requisitions
                (purchase_order_id, purchase_requisition_id)
            SELECT id, purchase_requisition_id
            FROM purchase_orders
            WHERE purchase_requisition_id IS NOT NULL
            ON CONFLICT DO NOTHING
            """
        )
    )

    op.add_column(
        "purchase_orders",
        sa.Column("expiry_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "purchase_orders",
        sa.Column(
            "receipt_tolerance_percent",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="0",
        ),
    )

    op.add_column(
        "goods_receipts",
        sa.Column(
            "destination_type",
            sa.String(30),
            nullable=False,
            server_default="INVENTORY",
        ),
    )
    op.add_column(
        "goods_receipts",
        sa.Column("warehouse_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_goods_receipts_warehouse_id",
        "goods_receipts",
        ["warehouse_id"],
    )
    op.create_foreign_key(
        "fk_goods_receipts_warehouse_id",
        "goods_receipts",
        "warehouses",
        ["warehouse_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.execute(
        sa.text(
            """
            ALTER TABLE inventory
            DROP CONSTRAINT IF EXISTS inventory_product_id_key
            """
        )
    )
    op.add_column(
        "inventory",
        sa.Column("warehouse_id", sa.Integer(), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE inventory
            SET warehouse_id = (
                SELECT id FROM warehouses
                WHERE code = 'MAIN'
                LIMIT 1
            )
            WHERE warehouse_id IS NULL
            """
        )
    )
    op.alter_column("inventory", "warehouse_id", nullable=False)
    op.create_index(
        "ix_inventory_warehouse_id",
        "inventory",
        ["warehouse_id"],
    )
    op.create_foreign_key(
        "fk_inventory_warehouse_id",
        "inventory",
        "warehouses",
        ["warehouse_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        "uq_inventory_product_warehouse",
        "inventory",
        ["product_id", "warehouse_id"],
    )

    op.add_column(
        "stock_movements",
        sa.Column("warehouse_id", sa.Integer(), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE stock_movements
            SET warehouse_id = (
                SELECT id FROM warehouses
                WHERE code = 'MAIN'
                LIMIT 1
            )
            WHERE warehouse_id IS NULL
            """
        )
    )
    op.alter_column("stock_movements", "warehouse_id", nullable=False)
    op.create_index(
        "ix_stock_movements_warehouse_id",
        "stock_movements",
        ["warehouse_id"],
    )
    op.create_foreign_key(
        "fk_stock_movements_warehouse_id",
        "stock_movements",
        "warehouses",
        ["warehouse_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.add_column(
        "warehouses",
        sa.Column("address", sa.Text(), nullable=True),
    )

    op.create_table(
        "chart_of_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_number", sa.String(30), nullable=False),
        sa.Column("account_name", sa.String(150), nullable=False),
        sa.Column("account_type", sa.String(30), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("account_number", name="uq_coa_account_number"),
    )

    op.create_table(
        "account_payables",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column("purchase_order_id", sa.Integer(), nullable=True),
        sa.Column("invoice_number", sa.String(100), nullable=True),
        sa.Column("invoice_date", sa.Date(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="OPEN"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"]),
        sa.ForeignKeyConstraint(["purchase_order_id"], ["purchase_orders.id"], ondelete="SET NULL"),
    )

    op.create_table(
        "account_receipts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("goods_receipt_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("unit_cost", sa.Numeric(14, 4), nullable=False),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["goods_receipt_id"], ["goods_receipts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["account_id"], ["chart_of_accounts.id"]),
    )

    op.execute(
        sa.text(
            """
            INSERT INTO departments (code, name)
            VALUES
                ('PURCHASING', 'Purchasing'),
                ('WAREHOUSE', 'Warehouse'),
                ('FINANCE', 'Finance'),
                ('OPERATIONS', 'Operations'),
                ('MANAGEMENT', 'Management')
            ON CONFLICT DO NOTHING
            """
        )
    )

    op.execute(
        sa.text(
            """
            INSERT INTO chart_of_accounts
                (account_number, account_name, account_type)
            VALUES
                ('1100', 'Cash', 'ASSET'),
                ('1200', 'Inventory', 'ASSET'),
                ('2100', 'Account Payable', 'LIABILITY'),
                ('5100', 'Purchase Expense', 'EXPENSE'),
                ('5200', 'Direct Consumption Expense', 'EXPENSE')
            ON CONFLICT DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.drop_table("account_receipts")
    op.drop_table("account_payables")
    op.drop_table("chart_of_accounts")
    op.drop_column("warehouses", "address")
    op.drop_constraint("fk_stock_movements_warehouse_id", "stock_movements", type_="foreignkey")
    op.drop_index("ix_stock_movements_warehouse_id", table_name="stock_movements")
    op.drop_column("stock_movements", "warehouse_id")
    op.drop_constraint("uq_inventory_product_warehouse", "inventory", type_="unique")
    op.drop_constraint("fk_inventory_warehouse_id", "inventory", type_="foreignkey")
    op.drop_index("ix_inventory_warehouse_id", table_name="inventory")
    op.drop_column("inventory", "warehouse_id")
    op.create_unique_constraint("inventory_product_id_key", "inventory", ["product_id"])
    op.drop_constraint("fk_goods_receipts_warehouse_id", "goods_receipts", type_="foreignkey")
    op.drop_index("ix_goods_receipts_warehouse_id", table_name="goods_receipts")
    op.drop_column("goods_receipts", "warehouse_id")
    op.drop_column("goods_receipts", "destination_type")
    op.drop_column("purchase_orders", "receipt_tolerance_percent")
    op.drop_column("purchase_orders", "expiry_date")
    op.drop_table("purchase_order_requisitions")
    op.drop_constraint("fk_users_department_id", "users", type_="foreignkey")
    op.drop_index("ix_users_department_id", table_name="users")
    op.drop_column("users", "department_id")
    op.drop_table("departments")
