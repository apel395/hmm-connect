"""create inventory table

Revision ID: 30e2a0472577
Revises: inventory_stock
Create Date: 2026-07-16 10:14:29.913294

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "30e2a0472577"

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "inventory_stock"

branch_labels: Union[
    str,
    Sequence[str],
    None,
] = None

depends_on: Union[
    str,
    Sequence[str],
    None,
] = None


def upgrade() -> None:
    op.create_table(
        "inventory",
        sa.Column(
            "id",
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
            sa.Numeric(
                precision=14,
                scale=4,
            ),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "average_cost",
            sa.Numeric(
                precision=14,
                scale=4,
            ),
            nullable=False,
            server_default="0",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id"),
    )

    op.create_index(
        "ix_inventory_product_id",
        "inventory",
        ["product_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_inventory_product_id",
        table_name="inventory",
    )

    op.drop_table("inventory")