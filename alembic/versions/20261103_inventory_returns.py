"""Source-linked partial supplier returns and replacement receipts."""
from alembic import op
import sqlalchemy as sa

revision = '20261103_inventory_returns'
down_revision = '20261102_pph_categories'
branch_labels = None
depends_on = None


def upgrade():
    from app.models.inventory_return import InventoryReturn, InventoryReturnItem, InventoryReplacement
    bind = op.get_bind()
    InventoryReturn.__table__.create(bind)
    InventoryReturnItem.__table__.create(bind)
    InventoryReplacement.__table__.create(bind)
    op.add_column('stock_movements', sa.Column('recorded_value', sa.Numeric(18, 2), nullable=True))
    op.add_column('goods_receipt_items', sa.Column('replacement_line_value', sa.Numeric(18, 2), nullable=True))
    # Preserve warehouse carrying-cost precision on replacement Receiving lines.
    for table in ('goods_receipt_items', 'stock_movements'):
        op.alter_column(table, 'unit_cost', existing_type=sa.Numeric(12, 2), type_=sa.Numeric(18, 4), existing_nullable=False)


def downgrade():
    bind = op.get_bind()
    for table in ('goods_receipt_items', 'stock_movements'):
        if bind.execute(sa.text(f'SELECT 1 FROM {table} WHERE unit_cost <> ROUND(unit_cost, 2) LIMIT 1')).first():
            raise RuntimeError('Four-decimal inventory costs exist; preserve their precision before downgrade')
    for table in ('inventory_return_replacements', 'inventory_return_items', 'inventory_returns'):
        if bind.execute(sa.text(f'SELECT 1 FROM {table} LIMIT 1')).first():
            raise RuntimeError('Inventory return records exist; do not discard their audit trail')
    if bind.execute(sa.text('SELECT 1 FROM stock_movements WHERE recorded_value IS NOT NULL LIMIT 1')).first():
        raise RuntimeError('Return valuation snapshots exist; do not discard them')
    op.drop_column('stock_movements', 'recorded_value')
    op.drop_column('goods_receipt_items', 'replacement_line_value')
    op.drop_table('inventory_return_replacements')
    op.drop_table('inventory_return_items')
    op.drop_table('inventory_returns')
    for table in ('goods_receipt_items', 'stock_movements'):
        op.alter_column(table, 'unit_cost', existing_type=sa.Numeric(18, 4), type_=sa.Numeric(12, 2), existing_nullable=False)
