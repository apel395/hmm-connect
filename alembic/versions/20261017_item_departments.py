"""Optional department ownership for Item Master.

Revision ID: 20261017_item_departments
Revises: 20261016_receiving_lines
"""
from alembic import op
import sqlalchemy as sa
revision = '20261017_item_departments'
down_revision = '20261016_receiving_lines'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('item_departments',
        sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id'), primary_key=True),
        sa.Column('department_id', sa.Integer(), sa.ForeignKey('departments.id'), nullable=False))
    op.create_index('ix_item_departments_department_id', 'item_departments', ['department_id'])


def downgrade():
    op.drop_table('item_departments')
