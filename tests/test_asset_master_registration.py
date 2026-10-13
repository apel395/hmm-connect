from types import SimpleNamespace
from datetime import date
from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.models import Base
from app.models.product import Product
from app.models.fixed_asset import FixedAsset
from app.models.chart_of_account import ChartOfAccount
from app.models.inventory import Inventory
from app.models.journal_entry import JournalEntry
from app.models.general_ledger import GeneralLedger
from app.services.fixed_asset_service import FixedAssetService

@pytest.fixture
def db():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(ChartOfAccount(id=1, account_number='100-900-100', account_name='Linen',
               account_type='ASSET', normal_balance='DEBIT', is_active=True, is_posting=True))
        db.commit()
        yield db
    engine.dispose()


def item(db):
    p = Product(code='4-200101', name='Synthetic hotel towel', group_code='4', group_name='ASSET',
        subgroup_code='4-2', subgroup_name='FURNITURE', uom='PCS', usage_uom='PCS',
        item_type='BUY', catalog_type='HOTEL', inventory_treatment='FIXED_ASSET', asset_account_id=1)
    db.add(p); db.commit()
    return p


def test_master_automatically_registers_unvalued_asset_once(db):
    p = item(db)
    asset = db.query(FixedAsset).one()
    assert asset.product_id == p.id and asset.asset_account_id == 1
    assert asset.status == 'PENDING_REGISTRATION'
    assert asset.acquisition_date is None and asset.acquisition_cost is None and asset.net_book_value is None
    assert not FixedAssetService(db).actions(asset)['can_capitalize']
    assert db.query(Inventory).count() == db.query(JournalEntry).count() == db.query(GeneralLedger).count() == 0
    p.name = 'Synthetic updated towel'; db.commit()
    assert db.query(FixedAsset).count() == 1
    assert db.query(FixedAsset).one().asset_name == p.name


def test_pending_registration_and_master_roll_back_together(db):
    p = Product(code='4-200102', name='Rollback towel', group_code='4', group_name='ASSET',
        subgroup_code='4-2', subgroup_name='FURNITURE', uom='PCS', usage_uom='PCS', item_type='BUY',
        catalog_type='HOTEL', inventory_treatment='FIXED_ASSET', asset_account_id=1)
    db.add(p); db.flush(); db.flush(); db.rollback()
    assert db.query(Product).count() == db.query(FixedAsset).count() == 0


def test_unregistered_asset_cannot_capitalize(db):
    item(db)
    asset = db.query(FixedAsset).one()
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        FixedAssetService(db).capitalize(asset, SimpleNamespace(capitalization_date=date.today(),
            depreciation_start_date=date.today(), create_journal=False), SimpleNamespace(id=1))


def test_pending_records_do_not_enter_valuation_report(db, monkeypatch):
    from app.api.v1 import fixed_assets_core as api
    monkeypatch.setattr(api, 'access', lambda user: None)
    monkeypatch.setattr(api, 'resolve_organization_access', lambda db,user,**kw: {})
    item(db)
    report = api.fixed_asset_report(db=db, user=SimpleNamespace())
    assert report['items'] == [] and report['totals']['acquisition_cost'] == Decimal('0')


def test_invoice_reuses_master_registration_and_keeps_source_amount(db):
    from sqlalchemy import insert
    from app.models.supplier_invoice import SupplierInvoice, SupplierInvoiceLine
    from app.services.invoice_asset_registration import register_invoice_asset
    p = item(db)
    pending_id = db.query(FixedAsset).one().id
    db.execute(insert(SupplierInvoice).values(id=611, internal_invoice_number='INV-611', supplier_invoice_number='SOURCE-1',
        supplier_id=1, invoice_date=date(2026,1,8), business_unit_id=1, subtotal=500, tax_amount=0,
        total_amount=500, balance_amount=500, status='POSTED'))
    db.execute(insert(SupplierInvoiceLine).values(id=900, supplier_invoice_id=611, description='Synthetic towel',
        quantity=10, uom='PCS', unit_price=50, line_amount=500, product_id=p.id, account_id=1))
    db.commit()
    asset = register_invoice_asset(db, invoice=db.get(SupplierInvoice,611), line=db.get(SupplierInvoiceLine,900),
        account_id=1, journal=SimpleNamespace(id=1,status='POSTED',location_id=None,business_unit_id=1), user=SimpleNamespace(id=1))
    db.commit()
    assert asset.id == pending_id and db.query(FixedAsset).count() == 1
    assert asset.acquisition_cost == Decimal('500') and asset.acquisition_date == date(2026,1,8)
    assert asset.source_invoice_line_id == 900 and asset.status == 'PENDING_SETUP'
    assert db.query(JournalEntry).count() == db.query(GeneralLedger).count() == 0


def test_complete_registration_retains_identity_without_journal(db):
    from app.models.business_unit import BusinessUnit
    from app.models.fixed_asset import FixedAssetCategory
    from app.schemas.fixed_asset import AssetInput
    db.add(BusinessUnit(id=1,code='HOTEL',name='Hotel',is_active=True))
    db.add(ChartOfAccount(id=2,account_number='100-800-103',account_name='Accumulated depreciation',account_type='ASSET',normal_balance='CREDIT',is_active=True,is_posting=True))
    db.add(ChartOfAccount(id=3,account_number='700-500-133',account_name='Depreciation expense',account_type='EXPENSE',normal_balance='DEBIT',is_active=True,is_posting=True))
    db.add(FixedAssetCategory(id=1,code='LINEN',name='Linen',asset_account_id=1,accumulated_depreciation_account_id=2,
        depreciation_expense_account_id=3,default_useful_life_months=36,is_active=True))
    db.commit()
    p = item(db); asset = db.query(FixedAsset).one(); original_id = asset.id
    value = AssetInput(product_id=p.id,asset_name=p.name,asset_category_id=1,acquisition_date=date(2026,1,8),
        acquisition_cost=500,useful_life_months=36,business_unit_id=1,asset_account_id=1,
        accumulated_depreciation_account_id=2,depreciation_expense_account_id=3)
    FixedAssetService(db).complete_registration(asset,value,SimpleNamespace(id=1)); db.commit()
    assert asset.id == original_id and asset.status == 'DRAFT' and asset.acquisition_cost == Decimal('500')
    assert db.query(FixedAsset).count() == 1
    assert db.query(JournalEntry).count() == db.query(GeneralLedger).count() == 0


def test_asset_group_requires_fixed_asset_treatment():
    from app.api.v1.products import _validate_treatment
    from fastapi import HTTPException
    with pytest.raises(HTTPException, match='ASSET group'):
        _validate_treatment({'group_name': 'ASSET', 'item_type': 'BUY', 'inventory_treatment': 'STOCK', 'inventory_account_id': 1})
    _validate_treatment({'group_name': 'ASSET', 'item_type': 'BUY', 'inventory_treatment': 'FIXED_ASSET', 'asset_account_id': 1})
