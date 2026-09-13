"""Add BUY/SELL item type and sales groups

Products and item groups gain an ``item_type`` flag (BUY vs SELL). Sales
groups 5-8 (FOOD, BEVERAGE, ROOM, SERVICE) are seeded as SELL groups so the
master item module can separate purchase items from sale items. The previous
unique constraint on ``item_groups.name`` is dropped so sales groups may mirror
purchase group names.

Revision ID: 20260912_item_type_buy_sell
Revises: 20260907_payment_vouchers
"""

from alembic import op
import sqlalchemy as sa

revision = "20260912_item_type_buy_sell"
down_revision = "20260907_payment_vouchers"
branch_labels = None
depends_on = None


SELL_GROUPS = [
    ("5", "FOOD"),
    ("6", "BEVERAGE"),
    ("7", "ROOM"),
    ("8", "SERVICE"),
]


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("item_type", sa.String(length=4), nullable=False, server_default="BUY"),
    )
    op.create_index("ix_products_item_type", "products", ["item_type"])

    op.add_column(
        "item_groups",
        sa.Column("item_type", sa.String(length=4), nullable=False, server_default="BUY"),
    )
    op.create_index("ix_item_groups_item_type", "item_groups", ["item_type"])
    op.drop_constraint("item_groups_name_key", "item_groups", type_="unique")
    op.create_index("ix_item_groups_name", "item_groups", ["name"])

    for code, name in SELL_GROUPS:
        op.execute(
            sa.text(
                "INSERT INTO item_groups (code, name, item_type, is_active) "
                "SELECT :code, :name, 'SELL', TRUE "
                "WHERE NOT EXISTS (SELECT 1 FROM item_groups WHERE code = :code)"
            ).bindparams(code=code, name=name)
        )


def downgrade() -> None:
    for code, _ in SELL_GROUPS:
        op.execute(sa.text("DELETE FROM item_groups WHERE code = :code").bindparams(code=code))
    op.drop_index("ix_item_groups_name", table_name="item_groups")
    op.create_unique_constraint("item_groups_name_key", "item_groups", ["name"])
    op.drop_index("ix_item_groups_item_type", table_name="item_groups")
    op.drop_column("item_groups", "item_type")
    op.drop_index("ix_products_item_type", table_name="products")
    op.drop_column("products", "item_type")