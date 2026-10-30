"""Capture supplier invoice documents and classified charges at Receiving."""
from alembic import op
import sqlalchemy as sa
revision = '20261030_receiving_billing'
down_revision = '20261024_pos_operations'
branch_labels = None
depends_on = None
def upgrade():
    op.add_column('goods_receipts',sa.Column('supplier_document_total',sa.Numeric(18,2)))
    op.add_column('supplier_invoices',sa.Column('supplier_document_total',sa.Numeric(18,2)))
    for table in ('goods_receipts','supplier_invoices'):
        for n in ('shipping_fee_amount','admin_fee_amount','other_fee_amount'):
            op.add_column(table,sa.Column(n,sa.Numeric(18,2),nullable=False,server_default='0'))
        for n in ('shipping_fee_account_id','admin_fee_account_id','other_fee_account_id'):
            op.add_column(table,sa.Column(n,sa.Integer,sa.ForeignKey('chart_of_accounts.id'),nullable=True))
        op.add_column(table,sa.Column('other_fee_description',sa.String(250)))
        op.add_column(table,sa.Column('supplier_document_url',sa.Text()))
    op.add_column('goods_receipts',sa.Column('discount_amount',sa.Numeric(18,2),nullable=False,server_default='0'))
    for n in ('supplier_invoice_number','tax_invoice_number'):
        op.add_column('goods_receipts',sa.Column(n,sa.String(100)))
    for n in ('supplier_invoice_date','supplier_invoice_due_date','tax_invoice_date'):
        op.add_column('goods_receipts',sa.Column(n,sa.Date()))
def downgrade():
    op.drop_column('goods_receipts','supplier_document_total')
    op.drop_column('supplier_invoices','supplier_document_total')
    for n in ('supplier_invoice_date','supplier_invoice_due_date','tax_invoice_date'):
        op.drop_column('goods_receipts',n)
    for n in ('supplier_invoice_number','tax_invoice_number'):
        op.drop_column('goods_receipts',n)
    op.drop_column('goods_receipts','discount_amount')
    for table in ('goods_receipts','supplier_invoices'):
        for n in ('shipping_fee_account_id','admin_fee_account_id','other_fee_account_id','shipping_fee_amount','admin_fee_amount','other_fee_amount','other_fee_description','supplier_document_url'):
            op.drop_column(table,n)
