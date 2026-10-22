"""Link invoices to scoped AR; separate customer cash receipts."""
from alembic import op
import sqlalchemy as sa
revision = '20261022_pos_ar_invoices'
down_revision = '20261022_pos_revenue'
branch_labels = None
depends_on = None


def upgrade():
    for name, kind, target in [('invoice_due_date',sa.Date(),None),('receivable_account_id',sa.Integer(),'chart_of_accounts'),('ar_correction_journal_id',sa.Integer(),'journal_entries')]:
        op.add_column('sales_transactions',sa.Column(name,kind,nullable=True))
        if target:op.create_foreign_key('fk_sale_'+name,'sales_transactions',target,[name],['id'],ondelete='RESTRICT')
    for name, target in [('source_sale_id','sales_transactions'),('account_id','chart_of_accounts'),('location_id','locations'),('business_unit_id','business_units'),('department_id','departments')]:
        op.add_column('account_receivables',sa.Column(name,sa.Integer(),nullable=True))
        op.create_foreign_key('fk_ar_'+name,'account_receivables',target,[name],['id'],ondelete='RESTRICT')
    op.create_unique_constraint('uq_ar_source_sale','account_receivables',['source_sale_id'])
    for name,target in [('journal_entry_id','journal_entries'),('cash_account_id','chart_of_accounts')]:
        op.add_column('customer_payments',sa.Column(name,sa.Integer(),nullable=True))
        op.create_foreign_key('fk_customer_payment_'+name,'customer_payments',target,[name],['id'],ondelete='RESTRICT')
    op.add_column('customer_payments',sa.Column('request_key',sa.String(64),nullable=True))
    op.create_unique_constraint('uq_customer_payment_request','customer_payments',['request_key'])


def downgrade():
    op.drop_constraint('uq_customer_payment_request','customer_payments',type_='unique')
    op.drop_column('customer_payments','request_key')
    for name in ['cash_account_id','journal_entry_id']:
        op.drop_constraint('fk_customer_payment_'+name,'customer_payments',type_='foreignkey');op.drop_column('customer_payments',name)
    op.drop_constraint('uq_ar_source_sale','account_receivables',type_='unique')
    for name in ['department_id','business_unit_id','location_id','account_id','source_sale_id']:
        op.drop_constraint('fk_ar_'+name,'account_receivables',type_='foreignkey');op.drop_column('account_receivables',name)
    for name in ['ar_correction_journal_id','receivable_account_id']:
        op.drop_constraint('fk_sale_'+name,'sales_transactions',type_='foreignkey');op.drop_column('sales_transactions',name)
    op.drop_column('sales_transactions','invoice_due_date')
