from datetime import date
from decimal import Decimal
from io import BytesIO
from zipfile import ZipFile
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import insert
from app.models.fixed_asset import FixedAsset, FixedAssetDepreciationSchedule
from app.models.product import Product
from app.models.chart_of_account import ChartOfAccount
from app.models.journal_entry import JournalEntry
from app.schemas.fixed_asset import CategoryInput
from app.schemas.amortization import AmortizationCreate
from app.services.fixed_asset_service import FixedAssetService
from app.services.asset_useful_life import validate_useful_life
from app.services.item_asset_policy import is_utensil
from app.api.v1.fixed_assets_core import fixed_asset_report, depreciation_report, export_fixed_assets, export_depreciation
from scripts.cleanup_hotel_utensil_assets import cleanup
from test_reclassify_hotel_utensils_1020 import db as utensil_db
from test_asset_policy_1014 import asset
from test_organization_and_asset_delivery import db, ADMIN, scoped_user


def test_four_year_minimum_and_non_depreciable_land(db, asset):
    for months in (None, 0, 12, 47):
        with pytest.raises(HTTPException): validate_useful_life(months)
    for months in (48, 60, 240): validate_useful_life(months)
    validate_useful_life(None, depreciable=False)
    assert CategoryInput(code='LAND', name='Land', is_depreciable=False, asset_account_id=5).default_useful_life_months is None
    assert CategoryInput(code='E', name='Equipment', asset_account_id=4).default_useful_life_months == 48
    with pytest.raises(HTTPException):
        FixedAssetService(db).create_category(CategoryInput(code='SHORT', name='Short', asset_account_id=4,
            default_useful_life_months=47, accumulated_depreciation_account_id=3, depreciation_expense_account_id=2))
    payload = dict(name='Software', start_date=date(2026,1,1), original_cost=100,
        business_unit_id=1, asset_account_id=1, accumulated_amortization_account_id=3, amortization_expense_account_id=2)
    assert AmortizationCreate(**payload).useful_life_months == 48
    with pytest.raises(ValidationError): AmortizationCreate(**payload, useful_life_months=47)
    for code in ('100-900-101', '100-900-102', '100-900-103'):
        a=ChartOfAccount(account_number=code,account_name='Utensils',account_type='ASSET',normal_balance='DEBIT',is_active=True,is_posting=True)
        db.add(a);db.flush()
        with pytest.raises(HTTPException, match='utensils'):
            FixedAssetService(db).create_category(CategoryInput(code=code, name='Utensils',asset_account_id=a.id,
                accumulated_depreciation_account_id=3,depreciation_expense_account_id=2))


def test_complete_category_cleanup_includes_dishes_bowls_and_glassware(utensil_db):
    db=utensil_db
    for pid,name in [(7398,'UTEN - Chili Dish'),(7397,'UTEN - Cereal Bowl Medium'),(7396,'CHI - Welcome Drink / Glass Juice Blinkmat')]:
        db.execute(insert(Product).values(id=pid,code=f'4-2{pid:05d}',name=name,group_code='4',group_name='ASSET',
            subgroup_code='4-2',subgroup_name='FURNITURE',item_type='BUY',catalog_type='HOTEL',inventory_treatment='FIXED_ASSET',asset_account_id=3,is_active=True,uom='PCS',usage_uom='PCS'))
        db.execute(insert(FixedAsset).values(asset_number=f'FA-ITEM-{pid:08d}',asset_name=name,product_id=pid,
            asset_account_id=3,status='PENDING_REGISTRATION',source_type='ITEM_MASTER',acquisition_cost=None,net_book_value=None))
        assert is_utensil({'name':name})
    db.commit()
    result=cleanup(db);db.commit()
    assert result['removed_empty_assets']==16 and not db.query(FixedAsset).count()
    assert {p.group_name for p in db.query(Product)}=={'MATERIAL'}
    assert cleanup(db)['changed_items']==0
    assert not db.query(JournalEntry).count()


def test_cleanup_with_valued_record_rolls_back_every_item(utensil_db):
    db=utensil_db
    db.query(FixedAsset).first().acquisition_cost=100;db.commit()
    with pytest.raises(ValueError,match='valued'): cleanup(db)
    db.rollback()
    assert db.query(FixedAsset).count()==13
    assert {p.group_name for p in db.query(Product)}=={'ASSET'}


def test_reports_keep_planned_separate_and_exports_respect_login_scope(db, asset):
    asset.status='ACTIVE';asset.useful_life_months=36
    for month,status,value in [(10,'POSTED',Decimal('10')), (11,'PLANNED',Decimal('20')), (12,'SKIPPED',Decimal('70'))]:
        db.add(FixedAssetDepreciationSchedule(fixed_asset_id=asset.id,period_year=2026,period_month=month,
            period_start=date(2026,month,1),period_end=date(2026,month,28),opening_book_value=100,
            depreciation_amount=value,accumulated_depreciation=value,closing_book_value=100-value,status=status))
    db.add(FixedAsset(asset_number='OUTSIDE',asset_name='Other location',acquisition_date=date(2026,1,1),
        acquisition_cost=999,net_book_value=999,business_unit_id=2,location_id=2,department_id=3,created_by_id=1,asset_account_id=4))
    db.commit()
    user=scoped_user(True);user.roles[0].permissions=[type('Permission',(),{'code':'finance.manage'})()]
    report=depreciation_report(db=db,user=user)
    assert report['total_depreciation']==10 and report['planned_depreciation']==20
    filtered=depreciation_report(db=db,user=user,status='POSTED',date_from=date(2026,10,1),date_to=date(2026,10,31))
    assert len(filtered['items'])==1
    current=fixed_asset_report(db=db,user=user)
    assert current['totals']['acquisition_cost']==100 and current['items'][0]['policy_review']=='BELOW_MINIMUM_LIFE'
    for response in (export_fixed_assets(db=db,user=user),export_depreciation(db=db,user=user)):
        with ZipFile(BytesIO(response.body)) as z:
            assert 'Summary' in z.read('xl/workbook.xml').decode()
            xml=''.join(z.read(n).decode() for n in z.namelist() if n.startswith('xl/worksheets/'))
            assert 'OUTSIDE' not in xml and '999' not in xml
    with pytest.raises(HTTPException): fixed_asset_report(db=db,user=user,location_id=2)
    with pytest.raises(HTTPException): depreciation_report(db=db,user=user,date_from=date(2026,12,1),date_to=date(2026,1,1))
    assert asset.useful_life_months==36 and not db.query(JournalEntry).count()


def test_category_setup_is_audited_and_idempotent_without_changing_existing(db):
    from scripts.setup_asset_categories_1020 import POLICIES, setup
    from app.models.fixed_asset import FixedAssetCategory
    from app.models.audit_log import AuditLog
    for code,name,asset_code,accumulated in POLICIES:
        db.add(ChartOfAccount(account_number=asset_code,account_name=name,account_type='ASSET',normal_balance='DEBIT',is_active=True,is_posting=True))
        if accumulated and not db.query(ChartOfAccount).filter_by(account_number=accumulated).first():
            db.add(ChartOfAccount(account_number=accumulated,account_name=name,account_type='ASSET',normal_balance='CREDIT',is_active=True,is_posting=True))
            db.flush()
    db.commit()
    first=setup(db);db.commit()
    assert len([c for c in first['categories'] if c['action']=='CREATE'])==6
    assert db.query(FixedAssetCategory).count()==6 and db.query(AuditLog).count()==6
    land=db.query(FixedAssetCategory).filter_by(code='MMH-LAND').one()
    assert not land.is_depreciable and land.default_useful_life_months is None
    again=setup(db)
    assert all(c['action']=='EXISTING_UNCHANGED' for c in again['categories'])
    assert not db.query(JournalEntry).count() and not db.query(FixedAsset).count()


def test_amortization_export_preserves_legacy_values_and_access(db):
    from app.models.amortization import Amortization
    from app.api.v1.amortizations import export_amortizations
    for number,location,unit in [('IN',1,1),('OUTSIDE',2,2)]:
        db.add(Amortization(amortization_number=number,name=number,start_date=date(2026,1,1),original_cost=120,
            useful_life_months=12,net_book_value=120,business_unit_id=unit,location_id=location,
            asset_account_id=1,accumulated_amortization_account_id=1,amortization_expense_account_id=2,created_by_id=1))
    db.commit()
    user=scoped_user();user.roles[0].permissions=[type('Permission',(),{'code':'finance.manage'})()]
    with ZipFile(BytesIO(export_amortizations(db=db,user=user).body)) as z:
        xml=z.read('xl/worksheets/sheet1.xml').decode()
        assert 'OUTSIDE' not in xml and 'BELOW_MINIMUM_LIFE' in xml
    assert {a.useful_life_months for a in db.query(Amortization)}=={12}
    assert not db.query(JournalEntry).count()
