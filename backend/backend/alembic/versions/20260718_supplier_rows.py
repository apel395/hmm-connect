from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260718_supplier_rows"
down_revision: Union[str, Sequence[str], None] = "20260717_suppliers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "supplier_rows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "supplier_id",
            sa.Integer(),
            sa.ForeignKey("suppliers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("pic_name", sa.String(length=120), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("unit", sa.String(length=150), nullable=True),
        sa.Column("item", sa.Text(), nullable=True),
    )

    op.create_index(
        "ix_supplier_rows_supplier_id",
        "supplier_rows",
        ["supplier_id"],
    )

    op.execute(
        sa.text(
            """
            INSERT INTO supplier_rows (
                supplier_id,
                pic_name,
                phone,
                unit,
                item
            )
            SELECT
                id,
                pic_name,
                phone,
                NULL,
                items
            FROM suppliers
            WHERE pic_name IS NOT NULL
               OR phone IS NOT NULL
               OR items IS NOT NULL
            """
        )
    )

    op.drop_column("suppliers", "location")
    op.drop_column("suppliers", "pic_name")
    op.drop_column("suppliers", "email")
    op.drop_column("suppliers", "phone")
    op.drop_column("suppliers", "items")


def downgrade() -> None:
    op.add_column(
        "suppliers",
        sa.Column("location", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "suppliers",
        sa.Column("pic_name", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "suppliers",
        sa.Column("email", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "suppliers",
        sa.Column("phone", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "suppliers",
        sa.Column("items", sa.Text(), nullable=True),
    )

    op.execute(
        sa.text(
            """
            UPDATE suppliers s
            SET
                pic_name = r.pic_name,
                phone = r.phone,
                items = r.item
            FROM (
                SELECT DISTINCT ON (supplier_id)
                    supplier_id,
                    pic_name,
                    phone,
                    item
                FROM supplier_rows
                ORDER BY supplier_id, id
            ) r
            WHERE s.id = r.supplier_id
            """
        )
    )

    op.drop_index(
        "ix_supplier_rows_supplier_id",
        table_name="supplier_rows",
    )
    op.drop_table("supplier_rows")
