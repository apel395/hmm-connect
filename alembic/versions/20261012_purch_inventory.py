"""Direct Market List receiving links and explicit warehouse issue dates."""
from alembic import op
import sqlalchemy as sa
revision = '20261012_purch_inventory'
down_revision = '20261009_item_receiving'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('goods_receipts',sa.Column('market_list_id',sa.Integer(),nullable=True))
    op.create_foreign_key('fk_receipts_market_list','goods_receipts','market_lists',['market_list_id'],['id'])
    op.create_index('ix_goods_receipts_market_list_id','goods_receipts',['market_list_id'])
    op.add_column('goods_receipt_items',sa.Column('market_list_item_id',sa.Integer(),nullable=True))
    op.create_foreign_key('fk_receipt_items_market_list','goods_receipt_items','market_list_items',['market_list_item_id'],['id'])
    op.create_index('ix_goods_receipt_items_market_list_item_id','goods_receipt_items',['market_list_item_id'])
    op.add_column('store_issues',sa.Column('issue_date',sa.Date(),nullable=True))


def downgrade():
    op.drop_column('store_issues','issue_date')
    op.drop_index('ix_goods_receipt_items_market_list_item_id',table_name='goods_receipt_items')
    op.drop_constraint('fk_receipt_items_market_list','goods_receipt_items',type_='foreignkey')
    op.drop_column('goods_receipt_items','market_list_item_id')
    op.drop_index('ix_goods_receipts_market_list_id',table_name='goods_receipts')
    op.drop_constraint('fk_receipts_market_list','goods_receipts',type_='foreignkey')
    op.drop_column('goods_receipts','market_list_id')
