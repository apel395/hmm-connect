"""add item classification

Revision ID: e0cb776890fd
Revises: 0c460f5bd1b2
Create Date: 2026-07-15 15:59:46.063947

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e0cb776890fd'
down_revision: Union[str, Sequence[str], None] = '0c460f5bd1b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column(
            "code",
            sa.String(length=20),
            nullable=True,
        ),
    )

    products = sa.table(
        "products",
        sa.column("id", sa.Integer),
        sa.column("code", sa.String),
    )

    connection = op.get_bind()

    rows = connection.execute(
        sa.select(products.c.id)
        .order_by(products.c.id)
    ).fetchall()

    for index, row in enumerate(rows, start=1):
        connection.execute(
            products.update()
            .where(products.c.id == row.id)
            .values(
                code=f"1-{100000 + index}",
            )
        )

    op.alter_column(
        "products",
        "code",
        existing_type=sa.String(length=20),
        nullable=False,
    )

    op.create_unique_constraint(
        "uq_products_code",
        "products",
        ["code"],
    )

    op.create_index(
        "ix_products_code",
        "products",
        ["code"],
        unique=False,
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    op.drop_index(
        "ix_products_code",
        table_name="products",
    )

    op.drop_constraint(
        "uq_products_code",
        "products",
        type_="unique",
    )

    op.drop_column(
        "products",
        "code",
    )
    # ### end Alembic commands ###
