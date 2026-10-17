from types import SimpleNamespace

from test_item_auto_code import db, ADMIN
from app.api.v1.products import classification_catalog, classification_master, preview_item_code
from app.models.item_group import ItemGroup
from app.models.product import Product


def test_empty_selling_catalog_has_four_separate_usable_groups(db):
    catalog = classification_master(item_type="SELL", db=db)
    assert {row['name'] for row in catalog} == {'FOOD', 'BEVERAGE', 'ROOM', 'SERVICE'}
    assert all(row['item_type'] == 'SELL' for row in catalog)
    for row in catalog:
        code = preview_item_code(row['code'], '', 'SELL', db, ADMIN)['code']
        assert code.startswith(row['code'] + '-')
    # Listing and previews are read-only; they do not seed fake items or stock.
    assert db.query(Product).count() == 0
    assert db.query(ItemGroup).count() == 1
    assert {row['code'] for row in classification_master(item_type='BUY', db=db)} == {'1'}


def test_configured_sell_group_wins_without_subgroups_and_inactive_stays_hidden():
    groups = [
        SimpleNamespace(id=1, code='CUSTOM', name='Food', item_type='SELL', is_active=True,
                        subgroups=[SimpleNamespace(id=2, code='CUSTOM-1', name='Menu', is_active=True)]),
        SimpleNamespace(id=3, code='ROOMS', name='ROOM', item_type='SELL', is_active=False, subgroups=[]),
    ]
    catalog = classification_catalog(groups, [], 'SELL')
    assert len([row for row in catalog if row['name'].upper() == 'FOOD']) == 1
    assert next(row for row in catalog if row['code'] == 'CUSTOM')['subgroups'] == []
    assert not any(row['name'] == 'ROOM' for row in catalog)
    assert {row['name'] for row in catalog if row['id'] == 0} == {'BEVERAGE', 'SERVICE'}


def test_unfiltered_form_catalog_contains_sell_defaults_but_never_reuses_buy_group():
    group = SimpleNamespace(id=1, code='1', name='FOOD', item_type='BUY', is_active=True, subgroups=[])
    catalog = classification_catalog([group], [])
    assert next(row for row in catalog if row['item_type'] == 'BUY')['code'] == '1'
    assert next(row for row in catalog if row['item_type'] == 'SELL' and row['name'] == 'FOOD')['code'] != '1'


def test_hotel_and_catering_groups_and_code_validation(db):
    import pytest
    from fastapi import HTTPException
    hotel = classification_master(item_type='SELL', catalog_type='HOTEL', db=db)
    catering = classification_master(item_type='SELL', catalog_type='CATERING', db=db)
    assert {g['name'] for g in hotel} == {'FOOD', 'BEVERAGE', 'ROOM', 'SERVICE'}
    assert {g['name'] for g in catering} == {'FOOD', 'BEVERAGE', 'SERVICE'}
    assert all(g['subgroups'] == [] for g in hotel + catering)
    assert preview_item_code('S-ROOM', '', 'SELL', db, ADMIN, catalog_type='HOTEL')['code'] == 'S-ROOM-000001'
    with pytest.raises(HTTPException):
        preview_item_code('S-ROOM', '', 'SELL', db, ADMIN, catalog_type='CATERING')
    with pytest.raises(HTTPException):
        preview_item_code('S-FOOD', 'S-FOOD-1', 'SELL', db, ADMIN, catalog_type='HOTEL')


def test_sell_save_uses_group_sequence_and_edit_keeps_existing_code(db):
    import pytest
    from fastapi import HTTPException
    from app.api.v1.products import create_product, update_product
    from app.schemas.product import ProductCreate, ProductUpdate
    def item(name, catalog='HOTEL', group='S-FOOD', group_name='FOOD', **kwargs):
        return ProductCreate(name=name, item_type='SELL', catalog_type=catalog,
                             group_code=group, group_name=group_name,
                             subgroup_code='', subgroup_name='',
                             uom='PORTION', usage_uom='PORTION', inventory_treatment='NON_STOCK',
                             tax_category='NON_TAXABLE', **kwargs)
    first = create_product(item('Hotel lunch'), db, ADMIN)
    second = create_product(item('Project lunch', catalog='CATERING'), db, ADMIN)
    assert first.code == 'S-FOOD-000001'
    assert second.code == 'S-FOOD-000002'
    assert first.subgroup_code == first.subgroup_name == ''
    ident = first.id
    update_product(first.id, ProductUpdate(name='Hotel lunch revised'), db, ADMIN)
    assert first.id == ident and first.code == 'S-FOOD-000001'
    with pytest.raises(HTTPException):
        create_product(item('Catering room', catalog='CATERING', group='S-ROOM', group_name='ROOM'), db, ADMIN)
    with pytest.raises(HTTPException):
        update_product(first.id, ProductUpdate(subgroup_code='SUB'), db, ADMIN)
