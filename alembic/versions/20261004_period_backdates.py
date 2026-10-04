"""Allow controlled backdated entries in each accounting period."""
from alembic import op
import sqlalchemy as sa

revision = "20261004_period_backdates"
down_revision = "20261002_invoice_asset_register"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("fiscal_periods", sa.Column(
        "allow_backdated_entries", sa.Boolean(), nullable=False, server_default=sa.true(),
    ))


def downgrade():
    op.drop_column("fiscal_periods", "allow_backdated_entries")
