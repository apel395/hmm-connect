"""add item classification

Revision ID: 68ebca88c393
Revises: e0cb776890fd
Create Date: 2026-07-15 16:19:32.712919

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "68ebca88c393"

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "e0cb776890fd"

branch_labels: Union[str, Sequence[str], None] = None

depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -------------------------------------------------
    # ITEM GROUPS
    # -------------------------------------------------

    op.create_table(
        "item_groups",
        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "code",
            sa.String(length=10),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_index(
        "ix_item_groups_code",
        "item_groups",
        ["code"],
        unique=True,
    )

    # -------------------------------------------------
    # ITEM SUBGROUPS
    # -------------------------------------------------

    op.create_table(
        "item_subgroups",
        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "code",
            sa.String(length=10),
            nullable=False,
        ),
        sa.Column(
            "name",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "group_id",
            sa.Integer(),
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
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["item_groups.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_item_subgroups_code",
        "item_subgroups",
        ["code"],
        unique=True,
    )

    # -------------------------------------------------
    # DEFAULT CLASSIFICATION
    # -------------------------------------------------

    op.execute(
        """
        INSERT INTO item_groups (
            code,
            name,
            is_active
        )
        VALUES (
            '0',
            'GENERAL',
            TRUE
        )
        """
    )

    op.execute(
        """
        INSERT INTO item_subgroups (
            code,
            name,
            group_id,
            is_active
        )
        SELECT
            '0-0',
            'UNCLASSIFIED',
            id,
            TRUE
        FROM item_groups
        WHERE code = '0'
        """
    )

    # -------------------------------------------------
    # PRODUCT COLUMNS
    # -------------------------------------------------

    op.add_column(
        "products",
        sa.Column(
            "group_code",
            sa.String(length=10),
            nullable=True,
        ),
    )

    op.add_column(
        "products",
        sa.Column(
            "group_name",
            sa.String(length=50),
            nullable=True,
        ),
    )

    op.add_column(
        "products",
        sa.Column(
            "subgroup_code",
            sa.String(length=10),
            nullable=True,
        ),
    )

    op.add_column(
        "products",
        sa.Column(
            "subgroup_name",
            sa.String(length=100),
            nullable=True,
        ),
    )

    op.add_column(
        "products",
        sa.Column(
            "uom",
            sa.String(length=20),
            nullable=True,
        ),
    )

    op.add_column(
        "products",
        sa.Column(
            "usage_uom",
            sa.String(length=20),
            nullable=True,
        ),
    )

    op.add_column(
        "products",
        sa.Column(
            "conversion",
            sa.Numeric(
                precision=12,
                scale=4,
            ),
            nullable=True,
        ),
    )

    # -------------------------------------------------
    # BACKFILL EXISTING PRODUCTS
    # -------------------------------------------------

    op.execute(
        """
        UPDATE products
        SET
            group_code = '0',
            group_name = 'GENERAL',
            subgroup_code = '0-0',
            subgroup_name = 'UNCLASSIFIED',
            uom = 'Pcs',
            usage_uom = 'Pcs',
            conversion = 1
        WHERE group_code IS NULL
        """
    )

    # -------------------------------------------------
    # MAKE COLUMNS REQUIRED
    # -------------------------------------------------

    op.alter_column(
        "products",
        "group_code",
        existing_type=sa.String(length=10),
        nullable=False,
    )

    op.alter_column(
        "products",
        "group_name",
        existing_type=sa.String(length=50),
        nullable=False,
    )

    op.alter_column(
        "products",
        "subgroup_code",
        existing_type=sa.String(length=10),
        nullable=False,
    )

    op.alter_column(
        "products",
        "subgroup_name",
        existing_type=sa.String(length=100),
        nullable=False,
    )

    op.alter_column(
        "products",
        "uom",
        existing_type=sa.String(length=20),
        nullable=False,
    )

    op.alter_column(
        "products",
        "usage_uom",
        existing_type=sa.String(length=20),
        nullable=False,
    )

    op.alter_column(
        "products",
        "conversion",
        existing_type=sa.Numeric(
            precision=12,
            scale=4,
        ),
        nullable=False,
    )

    # -------------------------------------------------
    # PRODUCT INDEXES
    # -------------------------------------------------

    op.drop_index(
        "ix_products_sku",
        table_name="products",
    )

    op.drop_constraint(
        "uq_products_code",
        "products",
        type_="unique",
    )

    op.drop_index(
        "ix_products_code",
        table_name="products",
    )

    op.create_index(
        "ix_products_code",
        "products",
        ["code"],
        unique=True,
    )

    op.drop_column(
        "products",
        "sku",
    )

    op.drop_column(
        "products",
        "unit",
    )


def downgrade() -> None:
    op.add_column(
        "products",
        sa.Column(
            "unit",
            sa.VARCHAR(length=20),
            nullable=False,
        ),
    )

    op.add_column(
        "products",
        sa.Column(
            "sku",
            sa.VARCHAR(length=50),
            nullable=False,
        ),
    )

    op.drop_index(
        "ix_products_code",
        table_name="products",
    )

    op.create_index(
        "ix_products_code",
        "products",
        ["code"],
        unique=False,
    )

    op.create_unique_constraint(
        "uq_products_code",
        "products",
        ["code"],
    )

    op.create_index(
        "ix_products_sku",
        "products",
        ["sku"],
        unique=True,
    )

    op.drop_column(
        "products",
        "conversion",
    )

    op.drop_column(
        "products",
        "usage_uom",
    )

    op.drop_column(
        "products",
        "uom",
    )

    op.drop_column(
        "products",
        "subgroup_name",
    )

    op.drop_column(
        "products",
        "subgroup_code",
    )

    op.drop_column(
        "products",
        "group_name",
    )

    op.drop_column(
        "products",
        "group_code",
    )

    op.drop_index(
        "ix_item_subgroups_code",
        table_name="item_subgroups",
    )

    op.drop_table("item_subgroups")

    op.drop_index(
        "ix_item_groups_code",
        table_name="item_groups",
    )

    op.drop_table("item_groups")