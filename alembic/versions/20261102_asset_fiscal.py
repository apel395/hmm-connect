"""Separate fiscal profiles without modifying book assets or accounting balances."""
from alembic import op
import sqlalchemy as sa
revision = '20261102_asset_fiscal'
down_revision = '20261030_receiving_billing'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('fixed_asset_fiscal_profiles',
        sa.Column('fixed_asset_id', sa.Integer(), sa.ForeignKey('fixed_assets.id'), primary_key=True),
        sa.Column('group_code', sa.String(30), nullable=False),
        sa.Column('method', sa.String(30), nullable=False),
        sa.Column('fiscal_cost', sa.Numeric(18, 2), nullable=False),
        sa.Column('start_date', sa.Date()),
        sa.Column('useful_life_months', sa.Integer()),
        sa.Column('reference', sa.String(500), nullable=False),
        sa.Column('opening_date', sa.Date()),
        sa.Column('opening_book_value', sa.Numeric(18, 2)),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('updated_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint('fiscal_cost > 0', name='ck_asset_fiscal_positive_cost'),
        sa.CheckConstraint('opening_book_value IS NULL OR (opening_book_value >= 0 AND opening_book_value <= fiscal_cost)', name='ck_asset_fiscal_opening'))

def downgrade():
    op.drop_table('fixed_asset_fiscal_profiles')
