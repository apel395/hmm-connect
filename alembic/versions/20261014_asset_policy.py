"""Explicit non-depreciable asset category policy."""
from alembic import op
import sqlalchemy as sa
revision='20261014_asset_policy'
down_revision='20261013_asset_master_intake'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('fixed_asset_movements',sa.Column('journal_entry_id',sa.Integer(),nullable=True))
    op.create_foreign_key('fk_asset_movement_journal','fixed_asset_movements','journal_entries',['journal_entry_id'],['id'])
    op.add_column('fixed_assets',sa.Column('quantity',sa.Numeric(18,4),nullable=True))
    op.add_column('fixed_asset_categories',sa.Column('is_depreciable',sa.Boolean(),nullable=False,server_default=sa.true()))
    for field in ('default_useful_life_months','accumulated_depreciation_account_id','depreciation_expense_account_id'):
        op.alter_column('fixed_asset_categories',field,existing_type=sa.Integer(),nullable=True)

def downgrade():
    # Refuse downgrade until non-depreciable categories have been explicitly resolved.
    for field in ('default_useful_life_months','accumulated_depreciation_account_id','depreciation_expense_account_id'):
        op.alter_column('fixed_asset_categories',field,existing_type=sa.Integer(),nullable=False)
    op.drop_column('fixed_asset_categories','is_depreciable')
    op.drop_column('fixed_assets','quantity')
    op.drop_constraint('fk_asset_movement_journal','fixed_asset_movements',type_='foreignkey')
    op.drop_column('fixed_asset_movements','journal_entry_id')
