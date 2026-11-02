"""PPh groups are category defaults; posting accounts belong to individual assets."""
from types import SimpleNamespace
from fastapi import HTTPException
from app.models.fixed_asset import FixedAssetCategory
from app.models.audit_log import AuditLog
from app.schemas.asset_fiscal import GROUPS
from app.services.audit import record_audit

CODES = {'GROUP_1':'PPH-G1','GROUP_2':'PPH-G2','GROUP_3':'PPH-G3','GROUP_4':'PPH-G4',
         'BUILDING_PERMANENT':'PPH-PERM','BUILDING_NON_PERMANENT':'PPH-NONPERM','LAND':'PPH-LAND'}
LEGACY_SCRIPT_CODES = {'MMH-LAND','MMH-BUILDING','MMH-MECHANICAL','MMH-VEHICLE','MMH-FFE','MMH-OTHER','MMH-INVENTARIS','MMH-OTHER-999'}


def validate_group_category(value):
    code = value.fiscal_group_code
    if code not in GROUPS:
        raise HTTPException(422, 'Select a valid PPh asset group')
    depreciable = code != 'LAND'
    if value.is_depreciable != depreciable or value.default_useful_life_months != GROUPS[code][1]:
        raise HTTPException(422, 'Category life must match its PPh group; book life can be set per asset')
    if any(getattr(value,k) for k in ('asset_account_id','accumulated_depreciation_account_id','depreciation_expense_account_id')):
        raise HTTPException(422, 'PPh groups use per-asset posting accounts, not a shared COA')


def validate_group_account(group_code, account_code):
    if not group_code:
        return
    if group_code == 'LAND' and account_code != '100-600-100':
        raise HTTPException(422, 'Tanah requires the land COA')
    if group_code.startswith('BUILDING_') and account_code != '100-600-101':
        raise HTTPException(422, 'Building PPh groups require the building COA')
    if group_code.startswith('GROUP_') and account_code in ('100-600-100','100-600-101'):
        raise HTTPException(422, 'Groups 1–4 apply to non-building assets')


def provenance(db, category):
    logs = db.query(AuditLog).filter(AuditLog.entity_type=='FIXED_ASSET_CATEGORY', AuditLog.entity_id==category.id).order_by(AuditLog.id).all()
    creation = next((a for a in logs if a.action in ('ASSET_CATEGORY_CREATED','CREATE')), None)
    ours = bool(category.code in LEGACY_SCRIPT_CODES and creation and creation.action=='ASSET_CATEGORY_CREATED'
                and (creation.details or {}).get('batch')=='ASSET_POLICY_20261020')
    return {'source':'MMH_SETUP_SCRIPT' if ours else 'USER_OR_UNCONFIRMED',
            'creator':creation.actor_name if creation else None,
            'created_at':creation.created_at if creation else category.created_at,
            'replaceable':ours}


def setup_pph_categories(db, create=True):
    actor=SimpleNamespace(id=None, full_name='PPh category setup', roles=[])
    rows=[]
    for group, (name, life, _, _) in GROUPS.items():
        existing=db.query(FixedAssetCategory).filter(FixedAssetCategory.fiscal_group_code==group).first()
        if existing:
            rows.append({'code':existing.code,'action':'EXISTING_UNCHANGED','life':existing.default_useful_life_months});continue
        code=CODES[group];suffix=1
        while db.query(FixedAssetCategory.id).filter(FixedAssetCategory.code==code).first():
            suffix+=1;code=f'{CODES[group]}-{suffix}'
        if not create:
            rows.append({'code':code,'action':'AVAILABLE','life':life});continue
        category=FixedAssetCategory(code=code,name=name,fiscal_group_code=group,is_depreciable=group!='LAND',
            default_useful_life_months=life,default_residual_percentage=0,asset_account_id=None,
            accumulated_depreciation_account_id=None,depreciation_expense_account_id=None,is_active=True,
            description='')
        db.add(category);db.flush()
        record_audit(db,actor,'ASSET_CATEGORY_CREATED','FIXED_ASSET_CATEGORY',f'Create PPh category {code}',entity_id=category.id,
                     details={'batch':'PPH_CATEGORIES_20261102','group':group})
        rows.append({'code':code,'action':'CREATE','life':life})
    replaced=[]
    for category in db.query(FixedAssetCategory).filter(FixedAssetCategory.code.in_(LEGACY_SCRIPT_CODES),FixedAssetCategory.is_active.is_(True)).all():
        if provenance(db,category)['replaceable']:
            if not create:
                replaced.append(category.code);continue
            category.is_active=False
            record_audit(db,actor,'ASSET_CATEGORY_REPLACED','FIXED_ASSET_CATEGORY',f'Replaced script category {category.code} with PPh groups',entity_id=category.id,
                         details={'batch':'PPH_CATEGORIES_20261102','historical_assets_preserved':True})
            replaced.append(category.code)
    return {'categories':rows,'replaced_script_categories':replaced}
