from types import SimpleNamespace
from test_item_auto_code import db, ADMIN
from app.api.v1.products import create_product
from app.schemas.product import ProductCreate
from scripts import renumber_sell_items_1017 as script


def test_renumber_keeps_ids_avoids_collisions_and_is_idempotent(db, monkeypatch):
    monkeypatch.setattr(script, 'record_audit', lambda *a, **kw: SimpleNamespace())
    payload = dict(item_type='SELL', group_code='5', group_name='FOOD', subgroup_code='', subgroup_name='',
                   uom='EA', usage_uom='EA', inventory_treatment='NON_STOCK', tax_category='NON_TAXABLE')
    existing = create_product(ProductCreate(name='Existing numbered item', **payload), db, ADMIN)
    legacy = create_product(ProductCreate(name='Old item', code='S-FOOD-000001', **payload), db, ADMIN)
    legacy.group_code = 'S-FOOD'; db.commit()
    ident = legacy.id
    changes = script.renumber(db, ADMIN); db.commit()
    assert legacy.id == ident and legacy.code == '5-000002' and legacy.group_code == '5'
    assert existing.code == '5-000001'
    assert len(changes) == 1
    assert script.renumber(db, ADMIN) == []


def test_dry_run_rollback_and_buy_items_are_preserved(db, monkeypatch):
    from test_item_auto_code import payload
    monkeypatch.setattr(script, 'record_audit', lambda *a, **kw: SimpleNamespace())
    buy = create_product(payload(name='Buying item', code='S-FOOD-123456'), db, ADMIN)
    sell = create_product(ProductCreate(name='Old selling item', item_type='SELL', group_code='5',
                          group_name='FOOD', subgroup_code='', subgroup_name='', uom='EA', usage_uom='EA',
                          inventory_treatment='NON_STOCK', tax_category='NON_TAXABLE', code='S-FOOD-000007'), db, ADMIN)
    sell.group_code = 'S-FOOD'; db.commit()
    ident = sell.id
    assert len(script.renumber(db, ADMIN)) == 1
    db.rollback()
    db.expire_all()
    assert db.get(type(sell), ident).code == 'S-FOOD-000007'
    assert buy.code == 'S-FOOD-123456'


def test_prefix_replacement_preserves_available_sequence(db, monkeypatch):
    monkeypatch.setattr(script, 'record_audit', lambda *a, **kw: SimpleNamespace())
    item = create_product(ProductCreate(name='Keep sequence', item_type='SELL', group_code='5',
                          group_name='FOOD', subgroup_code='', subgroup_name='', uom='EA', usage_uom='EA',
                          inventory_treatment='NON_STOCK', tax_category='NON_TAXABLE', code='S-FOOD-000007'), db, ADMIN)
    script.renumber(db, ADMIN)
    assert item.code == '5-000007'
