"""Optional outlet checkout policy and immutable sale evidence; no balance rewrites."""
from alembic import op
import sqlalchemy as sa
revision = "20261104_pos_checkout"
down_revision = "20261104_catering_billing"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("pos_outlet_policies", sa.Column("checkout_settings", sa.JSON(), nullable=True))
    op.add_column("sales_transactions", sa.Column("checkout_snapshot", sa.JSON(), nullable=True))


def downgrade():
    db = op.get_bind()
    if db.execute(sa.text("SELECT 1 FROM pos_outlet_policies WHERE checkout_settings IS NOT NULL LIMIT 1")).first() or db.execute(sa.text("SELECT 1 FROM sales_transactions WHERE checkout_snapshot IS NOT NULL LIMIT 1")).first():
        raise RuntimeError("Checkout settings or sale evidence exist; downgrade would discard them")
    op.drop_column("sales_transactions", "checkout_snapshot")
    op.drop_column("pos_outlet_policies", "checkout_settings")
