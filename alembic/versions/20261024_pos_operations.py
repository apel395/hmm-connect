"""Outlet tables, open orders and cashier shifts; no historical backfill."""
from alembic import op
import sqlalchemy as sa
revision = '20261024_pos_operations'
down_revision = '20261022_pos_ar_invoices'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('pos_outlet_policies', sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('location_id',sa.Integer(),sa.ForeignKey('locations.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('department_id',sa.Integer(),sa.ForeignKey('departments.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('order_mode',sa.String(10),nullable=False),sa.UniqueConstraint('location_id','department_id',name='uq_pos_outlet_policy'),
        sa.CheckConstraint("order_mode IN ('TABLE','COUNTER','EVENT')",name='ck_pos_order_mode'))
    op.create_table('pos_tables',sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('location_id',sa.Integer(),sa.ForeignKey('locations.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('department_id',sa.Integer(),sa.ForeignKey('departments.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('name',sa.String(30),nullable=False),sa.Column('seats',sa.Integer(),nullable=False),sa.Column('is_active',sa.Boolean(),nullable=False),
        sa.UniqueConstraint('location_id','department_id','name',name='uq_pos_table_name'),sa.CheckConstraint('seats > 0',name='ck_pos_table_seats'))
    op.create_table('pos_cashier_sessions',sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('location_id',sa.Integer(),sa.ForeignKey('locations.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('department_id',sa.Integer(),sa.ForeignKey('departments.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('cashier_id',sa.Integer(),sa.ForeignKey('users.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('status',sa.String(10),nullable=False),sa.Column('opened_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('opening_cash',sa.Numeric(18,2),nullable=False),sa.Column('closed_at',sa.DateTime(timezone=True)),
        sa.Column('closed_by_id',sa.Integer(),sa.ForeignKey('users.id',ondelete='RESTRICT')),
        sa.Column('counted_cash',sa.Numeric(18,2)),sa.Column('expected_cash',sa.Numeric(18,2)),sa.Column('cash_difference',sa.Numeric(18,2)),sa.Column('difference_reason',sa.Text()),
        sa.CheckConstraint("status IN ('OPEN','CLOSED')",name='ck_pos_session_status'),sa.CheckConstraint('opening_cash >= 0',name='ck_pos_opening_cash'))
    op.create_index('uq_pos_open_cashier','pos_cashier_sessions',['location_id','department_id','cashier_id'],unique=True,postgresql_where=sa.text("status = 'OPEN'"))
    for table in ('pos_tables','pos_cashier_sessions'):
        for col in ('location_id','department_id'):
            op.create_index('ix_'+table+'_'+col,table,[col])
    op.create_index('ix_pos_cashier_sessions_cashier_id','pos_cashier_sessions',['cashier_id'])
    for name,target in [('pos_table_id','pos_tables'),('cashier_session_id','pos_cashier_sessions')]:
        op.add_column('sales_transactions',sa.Column(name,sa.Integer(),nullable=True))
        op.create_foreign_key('fk_sale_'+name,'sales_transactions',target,[name],['id'],ondelete='RESTRICT')
    op.create_index('ix_sales_transactions_cashier_session_id','sales_transactions',['cashier_session_id'])
    for name,length in [('order_mode',10),('event_name',200),('order_request_key',64)]:
        op.add_column('sales_transactions',sa.Column(name,sa.String(length),nullable=True))
    op.create_unique_constraint('uq_sale_order_request_key','sales_transactions',['order_request_key'])
    op.create_index('uq_pos_active_table','sales_transactions',['pos_table_id'],unique=True,postgresql_where=sa.text("status = 'DRAFT' AND pos_table_id IS NOT NULL"))


def downgrade():
    op.drop_index('uq_pos_active_table','sales_transactions')
    op.drop_constraint('uq_sale_order_request_key','sales_transactions',type_='unique')
    for name in ('order_request_key','event_name','order_mode'):op.drop_column('sales_transactions',name)
    op.drop_index('ix_sales_transactions_cashier_session_id','sales_transactions')
    for name in ('cashier_session_id','pos_table_id'):
        op.drop_constraint('fk_sale_'+name,'sales_transactions',type_='foreignkey');op.drop_column('sales_transactions',name)
    op.drop_table('pos_cashier_sessions');op.drop_table('pos_tables');op.drop_table('pos_outlet_policies')
