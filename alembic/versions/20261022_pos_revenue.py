"""Preserve a POS order's chosen operating revenue account."""
from alembic import op
import sqlalchemy as sa
revision = '20261022_pos_revenue'
down_revision = '20261022_pos_pbjt'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('sales_transactions', sa.Column('revenue_account_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_pos_sale_revenue_account', 'sales_transactions', 'chart_of_accounts', ['revenue_account_id'], ['id'], ondelete='RESTRICT')


def downgrade():
    op.drop_constraint('fk_pos_sale_revenue_account', 'sales_transactions', type_='foreignkey')
    op.drop_column('sales_transactions', 'revenue_account_id')
