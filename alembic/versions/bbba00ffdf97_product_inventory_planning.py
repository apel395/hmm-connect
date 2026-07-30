"""product inventory planning

Revision ID: bbba00ffdf97
Revises: 9ecc2d541a9f
Create Date: 2026-07-22 16:39:13.598566

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bbba00ffdf97'
down_revision: Union[str, Sequence[str], None] = '9ecc2d541a9f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():

    op.add_column(
        "products",
        sa.Column("minimum_stock", sa.Numeric(12,2), nullable=False, server_default=sa.text("0"))
    )

    op.add_column(
        "products",
        sa.Column("reorder_level", sa.Numeric(12,2), nullable=False, server_default=sa.text("0"))
    )

    op.add_column(
        "products",
        sa.Column("maximum_stock", sa.Numeric(12,2), nullable=False, server_default=sa.text("0"))
    )

    op.add_column(
        "products",
        sa.Column("lead_time_days", sa.Integer(), nullable=False, server_default=sa.text("0"))
    )

    op.add_column(
        "products",
        sa.Column("preferred_supplier_id", sa.Integer(), nullable=True)
    )

    op.add_column(
        "products",
        sa.Column("inventory_account_id", sa.Integer(), nullable=True)
    )

    op.add_column(
        "products",
        sa.Column("purchase_account_id", sa.Integer(), nullable=True)
    )

    op.add_column(
        "products",
        sa.Column("cogs_account_id", sa.Integer(), nullable=True)
    )

    op.create_foreign_key(
        "fk_product_supplier",
        "products",
        "suppliers",
        ["preferred_supplier_id"],
        ["id"],
    )

    op.create_foreign_key(
        "fk_product_inventory_account",
        "products",
        "chart_of_accounts",
        ["inventory_account_id"],
        ["id"],
    )

    op.create_foreign_key(
        "fk_product_purchase_account",
        "products",
        "chart_of_accounts",
        ["purchase_account_id"],
        ["id"],
    )

    op.create_foreign_key(
        "fk_product_cogs_account",
        "products",
        "chart_of_accounts",
        ["cogs_account_id"],
        ["id"],
    )

    op.alter_column(
        "products",
        "minimum_stock",
        server_default=None,
    )

    op.alter_column(
        "products",
        "reorder_level",
        server_default=None,
    )

    op.alter_column(
        "products",
        "maximum_stock",
        server_default=None,
    )

    op.alter_column(
        "products",
        "lead_time_days",
        server_default=None,
    )


def downgrade():

    op.drop_constraint(
        "fk_product_cogs_account",
        "products",
        type_="foreignkey",
    )

    op.drop_constraint(
        "fk_product_purchase_account",
        "products",
        type_="foreignkey",
    )

    op.drop_constraint(
        "fk_product_inventory_account",
        "products",
        type_="foreignkey",
    )

    op.drop_constraint(
        "fk_product_supplier",
        "products",
        type_="foreignkey",
    )

    op.drop_column(
        "products",
        "cogs_account_id",
    )

    op.drop_column(
        "products",
        "purchase_account_id",
    )

    op.drop_column(
        "products",
        "inventory_account_id",
    )

    op.drop_column(
        "products",
        "preferred_supplier_id",
    )

    op.drop_column(
        "products",
        "lead_time_days",
    )

    op.drop_column(
        "products",
        "maximum_stock",
    )

    op.drop_column(
        "products",
        "reorder_level",
    )

    op.drop_column(
        "products",
        "minimum_stock",
    )
