"""Per-document receiving discount account override."""
from alembic import op
import sqlalchemy as sa

revision = "20261128_receiving_discount_account"
down_revision = "20261105_pos_guests"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("goods_receipts", "supplier_invoices"):
        op.add_column(
            table,
            sa.Column(
                "discount_account_id",
                sa.Integer(),
                sa.ForeignKey("chart_of_accounts.id"),
                nullable=True,
            ),
        )


def downgrade():
    for table in ("supplier_invoices", "goods_receipts"):
        op.drop_column(table, "discount_account_id")
