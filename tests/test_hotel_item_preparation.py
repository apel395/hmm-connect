from scripts.prepare_hotel_items import build_plan, proposal


def source():
    return {'items': [dict(source_row=13, source_number=1, section_code='01', section_name='FOOD', legacy_code='100', name='Sample prepared portion', unit='PORSI', purchase=10.0, expense=-2.0), dict(source_row=14, source_number=2, section_code='01', section_name='FOOD', legacy_code='100', name='Sample prepared portion', unit='', purchase=0.0, expense=0.0)]}


def test_preserve_every_source_row_and_missing_units():
    data = source()
    assert len(data['items']) == 2
    assert sorted(r['source_number'] for r in data['items']) == [1, 2]
    rows = build_plan(data)
    assert len(rows) == 2
    assert sum('UNIT_MISSING' in r['issues'] for r in rows) == 1
    assert all(r['catalog_type'] == 'HOTEL' for r in rows)
    assert any(r['expense'] < 0 for r in rows)


def test_catering_match_does_not_reuse_catering_item():
    data = source()
    row = data['items'][0]
    products = [dict(id=99, name=row['name'], uom=row['unit'], catalog_type='CATERING', item_type='BUY')]
    planned = build_plan({'items': [row]}, products)[0]
    assert planned['existing_hotel_ids'] == []
    assert planned['catering_name_matches'] == [99]
    assert planned['action'] == 'NEW_HOTEL_ITEM'


def test_prepared_portion_does_not_become_warehouse_stock():
    row = source()['items'][0]
    result = proposal(row)
    assert result['inventory_treatment'] is None
    assert 'BUY_SELL_AND_READY_MEAL_USAGE_REVIEW' in result['issues']
