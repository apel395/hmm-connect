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


def test_configured_sell_group_and_subgroups_win_and_inactive_stays_hidden():
    groups = [
        SimpleNamespace(id=1, code='CUSTOM', name='Food', item_type='SELL', is_active=True,
                        subgroups=[SimpleNamespace(id=2, code='CUSTOM-1', name='Menu', is_active=True)]),
        SimpleNamespace(id=3, code='ROOMS', name='ROOM', item_type='SELL', is_active=False, subgroups=[]),
    ]
    catalog = classification_catalog(groups, [], 'SELL')
    assert len([row for row in catalog if row['name'].upper() == 'FOOD']) == 1
    assert next(row for row in catalog if row['code'] == 'CUSTOM')['subgroups'][0]['name'] == 'Menu'
    assert not any(row['name'] == 'ROOM' for row in catalog)
    assert {row['name'] for row in catalog if row['id'] == 0} == {'BEVERAGE', 'SERVICE'}


def test_unfiltered_form_catalog_contains_sell_defaults_but_never_reuses_buy_group():
    group = SimpleNamespace(id=1, code='1', name='FOOD', item_type='BUY', is_active=True, subgroups=[])
    catalog = classification_catalog([group], [])
    assert next(row for row in catalog if row['item_type'] == 'BUY')['code'] == '1'
    assert next(row for row in catalog if row['item_type'] == 'SELL' and row['name'] == 'FOOD')['code'] != '1'
