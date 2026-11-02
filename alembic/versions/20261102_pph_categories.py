"""PPh category groups, independent of asset posting accounts."""
from alembic import op
import sqlalchemy as sa
revision='20261102_pph_categories'
down_revision='20261102_asset_fiscal'
branch_labels=None
depends_on=None

GROUPS=[('PPH-G1','Kelompok 1','GROUP_1',48),('PPH-G2','Kelompok 2','GROUP_2',96),
        ('PPH-G3','Kelompok 3','GROUP_3',192),('PPH-G4','Kelompok 4','GROUP_4',240),
        ('PPH-PERM','Bangunan permanen','BUILDING_PERMANENT',240),
        ('PPH-NONPERM','Bangunan tidak permanen','BUILDING_NON_PERMANENT',120),
        ('PPH-LAND','Tanah','LAND',None)]
LEGACY={'MMH-LAND','MMH-BUILDING','MMH-MECHANICAL','MMH-VEHICLE','MMH-FFE','MMH-OTHER','MMH-INVENTARIS','MMH-OTHER-999'}

def upgrade():
    with op.batch_alter_table('fixed_asset_categories') as batch:
        batch.alter_column('asset_account_id',existing_type=sa.Integer(),nullable=True)
        batch.add_column(sa.Column('fiscal_group_code',sa.String(30),nullable=True))
    conn=op.get_bind()
    categories=sa.Table('fixed_asset_categories',sa.MetaData(),autoload_with=conn)
    audit=sa.Table('audit_logs',sa.MetaData(),autoload_with=conn)
    for base,name,group,life in GROUPS:
        if conn.execute(sa.select(categories.c.id).where(categories.c.fiscal_group_code==group)).first(): continue
        code=base;suffix=1
        while conn.execute(sa.select(categories.c.id).where(categories.c.code==code)).first():
            suffix+=1;code=f'{base}-{suffix}'
        result=conn.execute(categories.insert().values(code=code,name=name,fiscal_group_code=group,is_depreciable=group!='LAND',
            default_useful_life_months=life,default_residual_percentage=0,asset_account_id=None,
            accumulated_depreciation_account_id=None,depreciation_expense_account_id=None,is_active=True,description=''))
        conn.execute(audit.insert().values(action='ASSET_CATEGORY_CREATED',entity_type='FIXED_ASSET_CATEGORY',entity_id=result.inserted_primary_key[0],
            summary=f'Create PPh category {code}',actor_name='System migration',details={'batch':'PPH_CATEGORIES_20261102','group':group}))
    old=conn.execute(sa.select(categories).where(categories.c.code.in_(LEGACY),categories.c.is_active.is_(True))).mappings().all()
    for category in old:
        creation=conn.execute(sa.select(audit).where(audit.c.entity_type=='FIXED_ASSET_CATEGORY',audit.c.entity_id==category['id'],
            audit.c.action.in_(['ASSET_CATEGORY_CREATED','CREATE'])).order_by(audit.c.id)).mappings().first()
        if creation and creation['action']=='ASSET_CATEGORY_CREATED' and (creation['details'] or {}).get('batch')=='ASSET_POLICY_20261020':
            conn.execute(categories.update().where(categories.c.id==category['id']).values(is_active=False))
            conn.execute(audit.insert().values(action='ASSET_CATEGORY_REPLACED',entity_type='FIXED_ASSET_CATEGORY',entity_id=category['id'],
                summary=f"Replaced script category {category['code']} with PPh groups",actor_name='System migration',
                details={'batch':'PPH_CATEGORIES_20261102','historical_assets_preserved':True}))

def downgrade():
    # Removing populated classification would lose user setup and audit evidence.
    # Roll forward for corrections; never delete category/asset history on downgrade.
    raise RuntimeError('PPh category setup contains audited data; use a reviewed forward migration')
