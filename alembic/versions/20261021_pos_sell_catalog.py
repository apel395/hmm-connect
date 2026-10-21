"""Allow location-based SELL sales without warehouse stock."""
from alembic import op
import sqlalchemy as sa
revision = "20261021_pos_sell_catalog"
down_revision = "20261020_department_outlets"
branch_labels = None
depends_on = None

def upgrade():
    op.alter_column("sales_transactions", "warehouse_id", existing_type=sa.Integer(), nullable=True)

def downgrade():
    # Refuse to invent a warehouse for location-only sales.
    op.alter_column("sales_transactions", "warehouse_id", existing_type=sa.Integer(), nullable=False)
