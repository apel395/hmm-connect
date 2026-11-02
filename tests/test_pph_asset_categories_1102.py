from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from io import BytesIO
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.models.fixed_asset import FixedAssetCategory, FixedAsset, FixedAssetFiscalProfile
from app.models.audit_log import AuditLog
from app.models.journal_entry import JournalEntry
from app.models.general_ledger import GeneralLedger
from app.schemas.fixed_asset import CategoryInput
from app.schemas.asset_fiscal import GROUPS
from app.services.asset_category_policy import setup_pph_categories, provenance
from app.services.fixed_asset_service import FixedAssetService
from app.api.v1.fixed_assets_core import categories, fiscal_groups, update_category
from test_organization_and_asset_delivery import db, ADMIN
from test_asset_policy_1014 import asset


def test_proven_script_categories_replaced_custom_and_asset_values_preserved(db,asset):
    legacy=FixedAssetCategory(code='MMH-FFE',name='Script equipment',asset_account_id=4,default_useful_life_months=48)
    custom=FixedAssetCategory(code='FA-0001',name='Kelompok I',asset_account_id=4,default_useful_life_months=48)
    # The code alone is never sufficient proof of our authorship.
    same_code=FixedAssetCategory(code='MMH-OTHER',name='User category',asset_account_id=4,default_useful_life_months=48)
    db.add_all([legacy,custom,same_code]);db.flush()
    db.add(AuditLog(action='ASSET_CATEGORY_CREATED',entity_type='FIXED_ASSET_CATEGORY',entity_id=legacy.id,summary='Create MMH-FFE',actor_name='EC2 asset category setup',details={'batch':'ASSET_POLICY_20261020'}))
    db.add(AuditLog(action='CREATE',entity_type='FIXED_ASSET_CATEGORY',entity_id=custom.id,summary='User created',actor_name='Finance'))
    asset.asset_category_id=legacy.id;db.commit()
    original=(asset.asset_category_id,asset.acquisition_cost,asset.net_book_value,asset.useful_life_months)
    result=setup_pph_categories(db);db.commit()
    assert result['replaced_script_categories']==['MMH-FFE']
    assert legacy.is_active is False and custom.is_active and same_code.is_active
    assert (asset.asset_category_id,asset.acquisition_cost,asset.net_book_value,asset.useful_life_months)==original
    assert provenance(db,custom)['creator']=='Finance'
    assert not provenance(db,same_code)['replaceable']
    pph=db.query(FixedAssetCategory).filter(FixedAssetCategory.fiscal_group_code.is_not(None)).all()
    assert len(pph)==7 and all(c.asset_account_id is None for c in pph)
    assert {c.fiscal_group_code:c.default_useful_life_months for c in pph}=={k:v[1] for k,v in GROUPS.items()}
    again=setup_pph_categories(db)
    assert all(c['action']=='EXISTING_UNCHANGED' for c in again['categories'])
    assert again['replaced_script_categories']==[]
    assert db.query(JournalEntry).count()==db.query(GeneralLedger).count()==db.query(FixedAssetFiscalProfile).count()==0


def test_group_category_uses_per_asset_coa_and_separate_fiscal_profile(db,asset):
    setup_pph_categories(db);db.commit()
    category=db.query(FixedAssetCategory).filter_by(fiscal_group_code='GROUP_2').one()
    service=FixedAssetService(db)
    original_cost=asset.acquisition_cost
    service.assign_category(asset,category.id);db.commit()
    assert asset.useful_life_months==96 and asset.asset_account_id==4
    assert asset.accumulated_depreciation_account_id==3 and asset.depreciation_expense_account_id==2
    assert asset.acquisition_cost==original_cost and not asset.schedules
    assert service.serialize(service.get(asset.id))['fiscal_group_code']=='GROUP_2'
    for invalid in ('LAND','BUILDING_PERMANENT','BUILDING_NON_PERMANENT'):
        bad=db.query(FixedAssetCategory).filter_by(fiscal_group_code=invalid).one()
        with pytest.raises(HTTPException):service.assign_category(asset,bad.id)
    assert db.query(FixedAssetFiscalProfile).count()==db.query(JournalEntry).count()==0
    data=CategoryInput(code=category.code,name=category.name,fiscal_group_code='GROUP_2',default_useful_life_months=96,description='Computers etc.')
    update_category(category.id,data,db,ADMIN)
    assert category.description=='Computers etc.'
    with pytest.raises(HTTPException): update_category(category.id,data.model_copy(update={'fiscal_group_code':'GROUP_1','default_useful_life_months':48}),db,ADMIN)
    result=categories(db,ADMIN)
    group2=next(c for c in result if c['id']==category.id)
    assert group2['straight_line_rate']=='12.5' and group2['declining_balance_rate']=='25'
    assert len(fiscal_groups(ADMIN))==7


def test_invalid_pph_defaults_rejected_without_fake_coa(db):
    service=FixedAssetService(db)
    base=CategoryInput(code='GROUP2',name='Kelompok 2',fiscal_group_code='GROUP_2',default_useful_life_months=96)
    service.validate_category(base)
    for changes in ({'fiscal_group_code':'UNKNOWN'},{'default_useful_life_months':48},{'asset_account_id':1},{'is_depreciable':False}):
        with pytest.raises(HTTPException):service.validate_category(base.model_copy(update=changes))


def test_pph_migration_seeds_groups_retires_only_proven_script_rows_without_changing_assets():
    spec=spec_from_file_location('pph_migration',Path(__file__).parents[1]/'alembic/versions/20261102_pph_categories.py')
    migration=module_from_spec(spec);spec.loader.exec_module(migration)
    engine=create_engine('sqlite://')
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE fixed_asset_categories (id INTEGER PRIMARY KEY,code VARCHAR(30) UNIQUE,name VARCHAR(120),is_depreciable BOOLEAN NOT NULL DEFAULT 1,default_useful_life_months INTEGER,default_residual_percentage NUMERIC DEFAULT 0,asset_account_id INTEGER NOT NULL,accumulated_depreciation_account_id INTEGER,depreciation_expense_account_id INTEGER,is_active BOOLEAN DEFAULT 1,description TEXT)'))
        conn.execute(text("CREATE TABLE audit_logs (id INTEGER PRIMARY KEY, action VARCHAR(50),entity_type VARCHAR(80),entity_id INTEGER,summary VARCHAR(255),actor_name VARCHAR(150),source VARCHAR(30) NOT NULL DEFAULT 'USER',details JSON)"))
        conn.execute(text('CREATE TABLE fixed_assets (id INTEGER PRIMARY KEY,asset_category_id INTEGER,acquisition_cost NUMERIC,net_book_value NUMERIC)'))
        conn.execute(text("INSERT INTO fixed_asset_categories (id,code,name,asset_account_id) VALUES (1,'MMH-FFE','Script category',215),(2,'FA-0001','User category',213)"))
        import json
        conn.execute(text("INSERT INTO audit_logs (action,entity_type,entity_id,summary,actor_name,details) VALUES ('ASSET_CATEGORY_CREATED','FIXED_ASSET_CATEGORY',1,'Script category','EC2 setup',:details)"),{'details':json.dumps({'batch':'ASSET_POLICY_20261020'})})
        conn.execute(text('INSERT INTO fixed_assets VALUES (1,1,5500000,5500000)'))
        with Operations.context(MigrationContext.configure(conn)):migration.upgrade()
        assert conn.execute(text('SELECT COUNT(*) FROM fixed_asset_categories WHERE fiscal_group_code IS NOT NULL')).scalar()==7
        assert conn.execute(text("SELECT COUNT(*) FROM audit_logs WHERE source='SYSTEM'")).scalar()==8
        assert conn.execute(text('SELECT is_active FROM fixed_asset_categories WHERE id=1')).scalar()==0
        assert conn.execute(text('SELECT is_active FROM fixed_asset_categories WHERE id=2')).scalar()==1
        assert tuple(conn.execute(text('SELECT asset_category_id,acquisition_cost,net_book_value FROM fixed_assets')).one())==(1,5500000,5500000)
        assert conn.execute(text('SELECT asset_account_id FROM fixed_asset_categories WHERE code=\'PPH-G2\'')).scalar() is None
    engine.dispose()


def test_custom_code_collision_and_read_only_setup_preview(db):
    custom=FixedAssetCategory(code='PPH-G1',name='User-defined code',asset_account_id=1,default_useful_life_months=48)
    db.add(custom);db.commit()
    preview=setup_pph_categories(db,create=False)
    assert preview['categories'][0]['code']=='PPH-G1-2'
    assert all(r['action']=='AVAILABLE' for r in preview['categories'])
    assert db.query(FixedAssetCategory).count()==1 and db.query(AuditLog).count()==0
    setup_pph_categories(db);db.commit()
    assert custom.name=='User-defined code' and custom.fiscal_group_code is None
    assert db.query(FixedAssetCategory).filter_by(code='PPH-G1-2').one().fiscal_group_code=='GROUP_1'
