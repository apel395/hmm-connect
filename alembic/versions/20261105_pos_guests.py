"""Nullable Hotel POS guest counts; preserve all historical orders and balances."""
from alembic import op
import sqlalchemy as sa

revision = "20261105_pos_guests"
down_revision = "20261104_pos_checkout"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("sales_transactions", sa.Column("guest_count", sa.Integer(), nullable=True))
    op.create_check_constraint("ck_sales_guest_count_positive", "sales_transactions", "guest_count IS NULL OR guest_count > 0")


def downgrade():
    if op.get_bind().execute(sa.text("SELECT 1 FROM sales_transactions WHERE guest_count IS NOT NULL LIMIT 1")).first():
        raise RuntimeError("Guest counts exist; downgrade would discard order history")
    op.drop_constraint("ck_sales_guest_count_positive", "sales_transactions", type_="check")
    op.drop_column("sales_transactions", "guest_count")
