"""Supplier credit usage and audited return reversals; no historical data updates."""
from alembic import op
import sqlalchemy as sa

revision = '20261103_return_completion'
down_revision = '20261103_inventory_returns'
branch_labels = None
depends_on = None


def upgrade():
    from app.models.inventory_return import InventoryReturnEvent
    InventoryReturnEvent.__table__.create(op.get_bind())


def downgrade():
    if op.get_bind().execute(sa.text('SELECT 1 FROM inventory_return_events LIMIT 1')).first():
        raise RuntimeError('Return settlement/reversal history exists; preserve the audit trail')
    op.drop_table('inventory_return_events')
