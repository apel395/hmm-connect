"""Unvalued fixed asset registration from Item Master classification."""
from alembic import op
import sqlalchemy as sa
revision = '20261013_asset_master_intake'
down_revision = '20261012_purch_inventory'
branch_labels = None
depends_on = None
FIELDS = {'acquisition_date': sa.Date(), 'acquisition_cost': sa.Numeric(18,2),
          'business_unit_id': sa.Integer(), 'created_by_id': sa.Integer(), 'net_book_value': sa.Numeric(18,2)}

def upgrade():
    for name, kind in FIELDS.items(): op.alter_column('fixed_assets', name, existing_type=kind, nullable=True)
    op.create_check_constraint('ck_fixed_asset_registered_details', 'fixed_assets', "status = 'PENDING_REGISTRATION' OR (acquisition_date IS NOT NULL AND acquisition_cost IS NOT NULL AND business_unit_id IS NOT NULL AND created_by_id IS NOT NULL)")
    op.create_index('uq_fixed_asset_pending_item', 'fixed_assets', ['product_id'], unique=True,
                    postgresql_where=sa.text("source_type = 'ITEM_MASTER' AND status = 'PENDING_REGISTRATION'"))

def downgrade():
    # PostgreSQL refuses NOT NULL if incomplete registrations remain; never delete them.
    op.drop_index('uq_fixed_asset_pending_item', table_name='fixed_assets')
    op.drop_constraint('ck_fixed_asset_registered_details', 'fixed_assets', type_='check')
    for name, kind in FIELDS.items(): op.alter_column('fixed_assets', name, existing_type=kind, nullable=False)
