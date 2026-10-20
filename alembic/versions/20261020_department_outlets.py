"""Link Hotel outlets to their parent departments without rewriting transactions."""
from alembic import op
import sqlalchemy as sa
revision='20261020_department_outlets'
down_revision='20261017_item_departments'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('department_outlets',sa.Column('department_id',sa.Integer(),sa.ForeignKey('departments.id',ondelete='CASCADE'),primary_key=True),
        sa.Column('parent_department_id',sa.Integer(),sa.ForeignKey('departments.id',ondelete='RESTRICT'),nullable=False),
        sa.CheckConstraint('department_id <> parent_department_id',name='ck_outlet_not_self'))
    op.create_index('ix_department_outlets_parent_department_id','department_outlets',['parent_department_id'])


def downgrade():
    op.drop_index('ix_department_outlets_parent_department_id',table_name='department_outlets')
    op.drop_table('department_outlets')
