"""Allow distinct-price lines for the same Catering invoice menu."""
from alembic import op
import sqlalchemy as sa

revision = '20261104_catering_prices'
down_revision = '20261103_return_completion'
branch_labels = None
depends_on = None


def upgrade():
    # Line IDs already identify every invoice line. Service validation still
    # rejects duplicate menu lines for normal POS/Hotel and matching prices.
    with op.batch_alter_table('sales_transaction_lines') as batch:
        batch.drop_constraint('uq_sales_transaction_product', type_='unique')


def downgrade():
    duplicate = op.get_bind().execute(sa.text('''SELECT 1 FROM sales_transaction_lines
        GROUP BY sales_transaction_id, product_id HAVING COUNT(*) > 1 LIMIT 1''')).first()
    if duplicate:
        raise RuntimeError('Distinct-price invoice lines exist; preserve their history before downgrade')
    with op.batch_alter_table('sales_transaction_lines') as batch:
        batch.create_unique_constraint('uq_sales_transaction_product', ['sales_transaction_id', 'product_id'])
