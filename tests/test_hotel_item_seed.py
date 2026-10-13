from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.models import Base
from app.models.chart_of_account import ChartOfAccount
from app.models.item_group import ItemGroup
from app.models.item_subgroup import ItemSubgroup
from app.models.product import Product
from app.models.inventory import Inventory
from app.models.journal_entry import JournalEntry
from app.models.general_ledger import GeneralLedger
from scripts.seed_hotel_items import SOURCE_SHA, apply_rows, database_snapshot, seed_plan


def source(*names, expense=0):
    return {'source_sha256': SOURCE_SHA, 'sheet': 'Synthetic test', 'items': [
        dict(source_row=i+10, source_number=i+1, section_code='01', section_name='FOOD',
             legacy_code='REPEATED', name=name, unit='KG', purchase=12.345, expense=expense)
        for i, name in enumerate(names or ('VEG - Synthetic carrot',))]}


@pytest.fixture
def db():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(ChartOfAccount(id=167, account_number='100-300-100', account_name='Inventory food',
                              account_type='ASSET', normal_balance='DEBIT', is_active=True, is_posting=True))
        group = ItemGroup(id=16, code='1', name='FOOD', item_type='BUY', is_active=True)
        group.subgroups = [ItemSubgroup(id=57, code='1-5', name='VEGETABLES', is_active=True)]
        db.add(group); db.commit()
        yield db
    engine.dispose()


def plan(db, data=None):
    return seed_plan(data or source(), *database_snapshot(db))


def test_seed_repeated_legacy_codes_generates_unique_master_codes_and_no_transactions(db):
    data = source('VEG - Synthetic carrot', 'VEG - Synthetic cabbage')
    rows = plan(db, data)
    created = apply_rows(db, data, rows)
    db.commit()
    assert [r['code'] for r in created] == ['1-500001', '1-500002']
    products = db.query(Product).order_by(Product.id).all()
    assert all(p.catalog_type == 'HOTEL' and p.item_type == 'BUY' for p in products)
    assert products[0].cost_price == Decimal('12.35')
    assert all(p.inventory_account_id == 167 and p.cogs_account_id is None for p in products)
    assert all(p.tax_category == 'REVIEW_REQUIRED' for p in products)
    assert db.query(Inventory).count() == db.query(JournalEntry).count() == db.query(GeneralLedger).count() == 0
    assert all(r['seed_status'] == 'EXISTING_HOTEL_ITEM' for r in plan(db, data))
    assert apply_rows(db, data, plan(db, data)) == []


def test_catering_same_name_keeps_separate_hotel_master(db):
    p = Product(code='1-500001', name='VEG - Synthetic carrot', catalog_type='CATERING', item_type='BUY',
                group_code='1', group_name='FOOD', subgroup_code='1-5', subgroup_name='VEGETABLES',
                uom='KG', usage_uom='KG', inventory_treatment='STOCK', inventory_account_id=167)
    db.add(p); db.commit()
    row = plan(db)[0]
    assert row['seed_status'] == 'CREATE' and row['catering_name_matches'] == [p.id]
    apply_rows(db, source(), [row]); db.commit()
    assert db.query(Product).count() == 2
    assert db.get(Product, p.id).catalog_type == 'CATERING'


def test_duplicate_names_invalid_units_and_unknown_equipment_defer(db):
    data = source('VEG - Duplicate', 'VEG - Duplicate', 'VEG - Missing unit', 'ENG - Equipment')
    data['items'][2]['unit'] = ''
    data['items'][3]['section_code'] = '10'
    assert all(r['seed_status'] == 'REVIEW' for r in plan(db, data))
    assert apply_rows(db, data, plan(db, data)) == []


def test_negative_expense_is_reference_only_not_seeded_as_value(db):
    row = plan(db, source(expense=-99))[0]
    assert row['seed_status'] == 'CREATE'
    assert row['new_product']['cost_price'] == '12.35'
    assert 'expense' not in row['new_product']


def test_invalid_account_and_changed_source_refuse(db):
    db.get(ChartOfAccount, 167).is_posting = False; db.flush()
    assert plan(db)[0]['seed_status'] == 'REVIEW'
    data = source(); data['source_sha256'] = 'changed'
    with pytest.raises(ValueError, match='Source workbook changed'): plan(db, data)


def test_audit_failure_rolls_back_products_as_one_transaction(db, monkeypatch):
    import app.services.audit as audit
    def fail(*args, **kwargs): raise RuntimeError('Audit unavailable')
    monkeypatch.setattr(audit, 'record_audit', fail)
    with pytest.raises(RuntimeError): apply_rows(db, source(), plan(db))
    db.rollback()
    assert db.query(Product).count() == 0


def test_operating_equipment_seed_registers_pending_asset_without_valuation(db):
    from app.models.fixed_asset import FixedAsset
    group = ItemGroup(id=19, code='4', name='ASSET', item_type='BUY', is_active=True)
    group.subgroups = [ItemSubgroup(id=75, code='4-2', name='FURNITURE', is_active=True)]
    db.add(group)
    db.add(ChartOfAccount(id=2, account_number='100-900-100', account_name='Linen', account_type='ASSET',
                          normal_balance='DEBIT', is_active=True, is_posting=True))
    db.commit()
    data = source('LINEN - Synthetic Bath Towel')
    data['items'][0].update(section_code='13', section_name='LINEN HK SUPPLIES', unit='PCS')
    rows = plan(db, data)
    assert rows[0]['seed_status'] == 'CREATE'
    apply_rows(db, data, rows); db.commit()
    product = db.query(Product).one()
    asset = db.query(FixedAsset).one()
    assert product.group_name == 'ASSET' and product.inventory_treatment == 'FIXED_ASSET'
    assert product.inventory_account_id is None and product.asset_account_id == 2
    assert asset.product_id == product.id and asset.asset_account_id == 2
    assert asset.acquisition_cost is None and asset.acquisition_date is None
    assert db.query(JournalEntry).count() == db.query(Inventory).count() == 0
