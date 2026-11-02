from datetime import date
from decimal import Decimal as D
from types import SimpleNamespace as NS
from io import BytesIO
from zipfile import ZipFile
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from app.schemas.asset_fiscal import FiscalProfileInput, GROUPS
from app.services.asset_fiscal_service import fiscal_schedule, fiscal_year_row
from app.services.asset_account_policy import ASSET_ACCOUNTS
from app.models.fixed_asset import FixedAssetFiscalProfile, FixedAssetDepreciationSchedule
from app.models.journal_entry import JournalEntry
from app.models.general_ledger import GeneralLedger
from app.models.audit_log import AuditLog
from app.api.v1.fixed_assets_core import update_fiscal_profile, get_fiscal_profile, fiscal_asset_report, export_fiscal_assets
from test_organization_and_asset_delivery import db, ADMIN, scoped_user
from test_asset_policy_1014 import asset


def profile(**kwargs):
    return FiscalProfileInput(group_code=kwargs.pop('group_code', 'GROUP_1'), method=kwargs.pop('method', 'STRAIGHT_LINE'), fiscal_cost=kwargs.pop('fiscal_cost', '4800'), start_date=kwargs.pop('start_date', date(2026, 10, 1)), **kwargs)


@pytest.mark.parametrize('group,months', [('GROUP_1',48),('GROUP_2',96),('GROUP_3',192),('GROUP_4',240),('BUILDING_PERMANENT',240),('BUILDING_NON_PERMANENT',120)])
def test_straight_line_final_rounding_and_group_lives(group, months):
    rows = fiscal_schedule(profile(group_code=group, fiscal_cost='1000.01'))
    assert len(rows) == months
    assert sum((r['depreciation'] for r in rows), D(0)) == D('1000.01')
    assert rows[-1]['closing'] == 0
    assert all(r['opening'] >= r['depreciation'] >= 0 for r in rows)


def test_declining_calendar_year_basis_proration_and_final_writeoff():
    rows = fiscal_schedule(profile(method='DECLINING_BALANCE'))
    assert [r['depreciation'] for r in rows[:3]] == [D(200)]*3
    assert rows[3]['period'] == '2027-01' and rows[3]['depreciation'] == D(175)
    assert len(rows) == 48 and rows[-1]['closing'] == 0
    assert sum((r['depreciation'] for r in rows), D(0)) == 4800


def test_land_building_and_snapshot_constraints():
    assert fiscal_schedule(profile(group_code='LAND', method='NONE', start_date=None)) == []
    for kwargs in [dict(group_code='BUILDING_PERMANENT',method='DECLINING_BALANCE'),
                   dict(group_code='LAND'), dict(opening_date=date(2026,11,30),opening_book_value=100),
                   dict(opening_date=date(2026,12,31)), dict(opening_date=date(2026,12,31),opening_book_value=9999),
                   dict(useful_life_months=300)]:
        with pytest.raises(ValidationError): profile(**kwargs)
    rows = fiscal_schedule(profile(group_code='BUILDING_PERMANENT', useful_life_months=300, reference='Tax election'))
    assert len(rows) == 300 and rows[0]['depreciation'] == 16
    snapshot = profile(opening_date=date(2026,12,31), opening_book_value='4000')
    rows = fiscal_schedule(snapshot)
    assert rows[0]['period'] == '2027-01' and rows[0]['opening'] == 4000
    assert len(rows)==45 and sum((r['depreciation'] for r in rows), D(0)) == 4000


def test_year_report_missing_future_disposal_and_opening():
    asset = NS(id=1,asset_number='FA',asset_name='Computer',acquisition_date=date(2026,10,1), schedules=[],movements=[])
    assert fiscal_year_row(asset,None,2026)['fiscal_depreciation'] is None
    assert fiscal_year_row(asset,profile(),2025)['opening']==0
    assert fiscal_year_row(asset,profile(),2026)['fiscal_depreciation']==300
    snapshot=profile(opening_date=date(2026,12,31),opening_book_value=4000)
    assert fiscal_year_row(asset,snapshot,2026)['status']=='BEFORE_FISCAL_OPENING'
    asset.movements=[NS(movement_type='DISPOSAL',movement_date=date(2027,2,1))]
    assert fiscal_year_row(asset,profile(),2027)['fiscal_depreciation']==200
    assert fiscal_year_row(asset,profile(),2027)['closing']==0
    assert fiscal_year_row(asset,profile(),2028)['opening']==0


def test_profile_version_audit_scope_no_financial_writes(db,asset):
    payload = profile()
    before = (asset.acquisition_cost,asset.net_book_value,asset.useful_life_months)
    out=update_fiscal_profile(asset.id,payload,db,ADMIN)
    assert out['version']==1
    assert get_fiscal_profile(asset.id,db,ADMIN)['schedule'][0]['depreciation']==100
    with pytest.raises(HTTPException) as err: update_fiscal_profile(asset.id,payload,db,ADMIN)
    assert err.value.status_code==409
    assert db.query(FixedAssetFiscalProfile).count()==1
    assert db.query(AuditLog).count()==1
    assert (asset.acquisition_cost,asset.net_book_value,asset.useful_life_months)==before
    assert db.query(JournalEntry).count()==db.query(GeneralLedger).count()==0
    assert db.query(FixedAssetDepreciationSchedule).count()==0
    with pytest.raises(HTTPException): get_fiscal_profile(asset.id,db,NS(id=99,roles=[]))
    other=scoped_user();other.default_location_id=2;other.location_id=2
    with pytest.raises(HTTPException): get_fiscal_profile(asset.id,db,other)
    with pytest.raises(HTTPException): update_fiscal_profile(asset.id,profile(group_code='BUILDING_PERMANENT',expected_version=1),db,ADMIN)
    updated=update_fiscal_profile(asset.id,profile(method='DECLINING_BALANCE',expected_version=1),db,ADMIN)
    assert updated['version']==2
    assert db.query(AuditLog).count()==2
    report=fiscal_asset_report(2026,db=db,user=ADMIN)
    assert report['totals']['fiscal_depreciation']==600
    assert report['totals']['difference']==-600
    with ZipFile(BytesIO(export_fiscal_assets(2026,db=db,user=ADMIN).body)) as z:
        assert b'Fiscal depreciation' in z.read('xl/worksheets/sheet2.xml')
    with pytest.raises(HTTPException): fiscal_asset_report(2026,location_id=2,db=db,user=scoped_user())
    assert db.query(JournalEntry).count()==0


def test_exact_coa_pairs_and_linen_exclusion(db,asset):
    from app.models.chart_of_account import ChartOfAccount
    from app.services.fixed_asset_service import FixedAssetService
    from app.schemas.fixed_asset import CategoryInput
    service=FixedAssetService(db)
    assert ASSET_ACCOUNTS['100-600-105']==('Inventaris','100-800-104')
    assert ASSET_ACCOUNTS['100-600-999'][1]=='100-800-999'
    wrong=ChartOfAccount(account_number='100-800-104',account_name='Inventaris accumulated',account_type='ASSET',normal_balance='CREDIT',is_active=True,is_posting=True)
    linen=ChartOfAccount(account_number='100-900-100',account_name='Linen',account_type='ASSET',normal_balance='DEBIT',is_active=True,is_posting=True)
    db.add_all([wrong,linen]);db.flush()
    data=CategoryInput(code='EQ2',name='Equipment',asset_account_id=4,accumulated_depreciation_account_id=wrong.id,depreciation_expense_account_id=2)
    with pytest.raises(HTTPException,match='100-800-103'): service.validate_accounts(data)
    with pytest.raises(HTTPException,match='linen'): service.validate_accounts(data.model_copy(update={'asset_account_id':linen.id}))


def test_linen_remains_quantity_stock_and_all_asset_intake_paths_reject_it(db,asset):
    from app.models.product import Product
    from app.models.chart_of_account import ChartOfAccount
    from app.services.asset_master_registration import register_master_asset
    from app.services.asset_item_master import ensure_asset_item
    from app.services.item_asset_policy import validate_asset_item
    from app.services.direct_coa_service import DirectCoaService
    linen = ChartOfAccount(account_number='100-900-100',account_name='Operating equipment - Linen',account_type='ASSET',normal_balance='DEBIT',is_active=True,is_posting=True)
    db.add(linen);db.flush()
    values=dict(name='Hotel towel',subgroup_name='LINEN HK SUPPLIES',inventory_treatment='FIXED_ASSET')
    with pytest.raises(HTTPException,match='quantity-controlled'): validate_asset_item(values)
    stock=Product(code='3-901000',name='Hotel towel',group_code='3',group_name='MATERIAL',subgroup_code='3-9',subgroup_name='LINEN HK SUPPLIES',item_type='BUY',catalog_type='HOTEL',inventory_treatment='STOCK',inventory_account_id=linen.id,uom='PCS',usage_uom='PCS',conversion=1,is_active=True)
    db.add(stock);db.commit()
    validate_asset_item(stock)
    assert register_master_asset(db,stock) is None
    assert DirectCoaService(db).inventory_account(stock).id==linen.id
    assert stock.uom=='PCS' and stock.inventory_treatment=='STOCK'
    with pytest.raises(HTTPException): ensure_asset_item(db,name='Hotel towel',account_id=linen.id,user=ADMIN)
    # Account guard also stops legacy linen whose imported subgroup was flattened to Furniture.
    with pytest.raises(HTTPException): register_master_asset(db,NS(item_type='BUY',is_active=True,inventory_treatment='FIXED_ASSET',name='Hotel towel',subgroup_name='FURNITURE',asset_account_id=linen.id))
    from app.models.fixed_asset import FixedAsset
    assert db.query(FixedAsset).count()==1 and db.query(JournalEntry).count()==0


def test_migration_creates_only_empty_fiscal_table_without_backfill():
    import importlib.util
    from pathlib import Path
    from sqlalchemy import create_engine, text, inspect
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    path=Path(__file__).parents[1]/'alembic/versions/20261102_asset_fiscal.py'
    spec=importlib.util.spec_from_file_location('asset_fiscal_migration',path)
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    engine=create_engine('sqlite://')
    with engine.begin() as conn:
        for table in ('fixed_assets','users','opening_balances','general_ledger'):
            conn.execute(text(f'CREATE TABLE {table} (id INTEGER PRIMARY KEY, amount NUMERIC)'))
            conn.execute(text(f'INSERT INTO {table} VALUES (1, 123.45)'))
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
            assert 'fixed_asset_fiscal_profiles' in inspect(conn).get_table_names()
            assert conn.execute(text('SELECT COUNT(*) FROM fixed_asset_fiscal_profiles')).scalar()==0
            migration.downgrade()
        for table in ('fixed_assets','opening_balances','general_ledger'):
            assert conn.execute(text(f'SELECT amount FROM {table}')).scalar()==123.45
    engine.dispose()


def test_fully_depreciated_legacy_opening_is_zero_not_restarted():
    old=profile(start_date=date(2020,1,1),opening_date=date(2025,12,31),opening_book_value=0)
    assert fiscal_schedule(old)==[]
    with pytest.raises(ValueError,match='zero fiscal opening'):
        fiscal_schedule(profile(start_date=date(2020,1,1),opening_date=date(2025,12,31),opening_book_value=100))
