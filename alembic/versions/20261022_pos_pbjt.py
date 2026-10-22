"""Snapshot POS tax type and its existing payable account."""
from alembic import op
import sqlalchemy as sa
revision = '20261022_pos_pbjt'
down_revision = '20261021_pos_sell_catalog'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('sales_transaction_lines', sa.Column('tax_type', sa.String(20), nullable=False, server_default='LEGACY'))
    op.add_column('sales_transaction_lines', sa.Column('tax_account_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_pos_line_tax_account', 'sales_transaction_lines', 'chart_of_accounts', ['tax_account_id'], ['id'], ondelete='RESTRICT')


def downgrade():
    op.drop_constraint('fk_pos_line_tax_account', 'sales_transaction_lines', type_='foreignkey')
    op.drop_column('sales_transaction_lines', 'tax_account_id')
    op.drop_column('sales_transaction_lines', 'tax_type')
