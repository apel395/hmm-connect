"""retain additional historical purchasing fields

Revision ID: 20260803_historical_fields
Revises: 20260803_historical_import
"""
from alembic import op
import sqlalchemy as sa

revision="20260803_historical_fields"
down_revision="20260803_historical_import"
branch_labels=None
depends_on=None

def upgrade():
    op.add_column("purchase_requisitions",sa.Column("department_id",sa.Integer(),sa.ForeignKey("departments.id",ondelete="SET NULL")))
    op.add_column("purchase_requisitions",sa.Column("location_id",sa.Integer(),sa.ForeignKey("locations.id",ondelete="SET NULL")))
    op.add_column("purchase_requisitions",sa.Column("requested_by_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="SET NULL")))
    op.create_index("ix_purchase_requisitions_department_id","purchase_requisitions",["department_id"])
    op.create_index("ix_purchase_requisitions_location_id","purchase_requisitions",["location_id"])
    op.add_column("purchase_orders",sa.Column("currency",sa.String(3),nullable=False,server_default="IDR"))
    op.add_column("purchase_orders",sa.Column("discount_amount",sa.Numeric(18,2),nullable=False,server_default="0"))
    op.add_column("purchase_orders",sa.Column("tax_amount",sa.Numeric(18,2),nullable=False,server_default="0"))
    op.add_column("goods_receipts",sa.Column("delivery_note_number",sa.String(100)))

def downgrade():
    op.drop_column("goods_receipts","delivery_note_number")
    op.drop_column("purchase_orders","tax_amount");op.drop_column("purchase_orders","discount_amount");op.drop_column("purchase_orders","currency")
    op.drop_index("ix_purchase_requisitions_location_id",table_name="purchase_requisitions")
    op.drop_index("ix_purchase_requisitions_department_id",table_name="purchase_requisitions")
    op.drop_column("purchase_requisitions","requested_by_id");op.drop_column("purchase_requisitions","location_id");op.drop_column("purchase_requisitions","department_id")
