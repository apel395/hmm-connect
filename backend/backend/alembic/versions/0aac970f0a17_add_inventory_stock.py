"""add inventory stock

Revision ID: inventory_stock
Revises: 68ebca88c393
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "inventory_stock"

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "68ebca88c393"

branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "warehouses",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
        ),
        sa.Column(
            "code",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column(
            "name",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "code",
            name="uq_warehouses_code",
        ),
    )

    op.create_table(
        "stock_transactions",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
        ),
        sa.Column(
            "product_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "warehouse_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "transaction_type",
            sa.String(length=30),
            nullable=False,
        ),
        sa.Column(
            "quantity",
            sa.Numeric(
                precision=14,
                scale=4,
            ),
            nullable=False,
        ),
        sa.Column(
            "unit_cost",
            sa.Numeric(
                precision=14,
                scale=4,
            ),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "reference",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "transaction_date",
            sa.Date(),
            nullable=False,
        ),
        sa.Column(
            "description",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id"],
            ["warehouses.id"],
        ),
    )

    op.execute(
        """
        INSERT INTO warehouses (
            code,
            name,
            is_active
        )
        VALUES (
            'MAIN',
            'Main Warehouse',
            TRUE
        )
        """
    )


def downgrade() -> None:
    op.drop_table("stock_transactions")
    op.drop_table("warehouses")