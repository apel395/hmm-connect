from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException

from test_store_request_flow import store_db, make_request
from test_inventory_date_account_totals import db, ADMIN
from app.api.v1.inventory import list_movements
from app.api.v1.store_requests import _detail, warehouse_availability
from app.models.inventory import Inventory
from app.models.journal_entry import JournalEntry
from app.models.general_ledger import GeneralLedger
from app.models.product import Product
from app.models.stock_movement import StockMovement
from app.models.warehouse import Warehouse
from app.schemas.store_request import StoreRequestIssueCreate, StoreRequestIssueItem
from app.services.store_request_service import StoreRequestService


def test_reference_cost_is_scoped_nullable_and_read_only(store_db):
    session, bu, department, location, warehouse, requester, store_user, products = store_db
    request = make_request(session, bu, department, location, warehouse, requester, products, [3, 2])
    inventory = Inventory(product_id=products[0].id, warehouse_id=warehouse.id,
                          quantity=10, average_cost=Decimal('12.3456'))
    session.add(inventory)
    session.commit()
    rows = warehouse_availability(warehouse.id, [products[0].id, products[1].id], session, requester)
    assert rows[0]['reference_unit_cost'] == Decimal('12.3456')
    assert rows[1]['available_stock'] == 0
    assert rows[1]['reference_unit_cost'] is None
    detail = _detail(session, request, requester)
    assert detail['items'][0]['estimated_value'] == Decimal('37.04')
    assert detail['items'][1]['estimated_value'] is None
    assert detail['estimated_total'] is None
    assert detail['price_basis'] == 'CURRENT_WAREHOUSE_AVERAGE'
    assert inventory.quantity == 10
    assert session.query(JournalEntry).count() == 0
    assert session.query(GeneralLedger).count() == 0
    other = Warehouse(code='OTHER', name='Other', location_id=location.id + 999, is_active=True)
    session.add(other)
    session.flush()
    with pytest.raises(HTTPException):
        warehouse_availability(other.id, [products[0].id], session, requester)


def test_live_estimate_does_not_revalue_posted_issue(store_db):
    session, bu, department, location, warehouse, requester, store_user, products = store_db
    request = make_request(session, bu, department, location, warehouse, requester, products[:1], [3])
    inventory = Inventory(product_id=products[0].id, warehouse_id=warehouse.id, quantity=10, average_cost=10)
    session.add(inventory)
    session.commit()
    assert _detail(session, request, requester)['estimated_total'] == Decimal('30.00')
    issue = StoreRequestService.create_issue(session, request_id=request.id,
        data=StoreRequestIssueCreate(items=[StoreRequestIssueItem(item_id=request.items[0].id, quantity=3)]), current_user=store_user)
    inventory.average_cost = 20
    session.commit()
    StoreRequestService.post_issue(session, issue_id=issue.id, current_user=store_user)
    movement = session.query(StockMovement).one()
    assert movement.unit_cost == 20
    original_gl = [(row.id, row.debit, row.credit) for row in session.query(GeneralLedger).order_by(GeneralLedger.id)]
    assert sum(row[1] for row in original_gl) == 60
    inventory.average_cost = 30
    session.commit()
    assert _detail(session, request, requester)['estimated_total'] == Decimal('90.00')
    assert movement.unit_cost == 20
    assert inventory.quantity == 7
    assert [(row.id, row.debit, row.credit) for row in session.query(GeneralLedger).order_by(GeneralLedger.id)] == original_gl
    with pytest.raises(HTTPException):
        StoreRequestService.post_issue(session, issue_id=issue.id, current_user=store_user)
    assert session.query(StockMovement).count() == 1


def test_return_source_filter_totals_and_pages_exclude_other_outs(db):
    product = Product(code='RET-TEST', name='Return test', group_code='1', group_name='Food',
                      subgroup_code='1', subgroup_name='Food', uom='PCS', usage_uom='PCS', is_active=True)
    warehouse = Warehouse(code='RET-WH', name='Return warehouse', is_active=True)
    db.add_all([product, warehouse])
    db.flush()
    for index, source in enumerate(['GOODS_RECEIPT_RETURN', 'STORE_REQUEST', 'GOODS_RECEIPT_RETURN'], 1):
        db.add(StockMovement(product_id=product.id, warehouse_id=warehouse.id, movement_type='OUT',
                             quantity=Decimal('-2'), unit_cost=Decimal('12.50'),
                             reference_type=source, reference_id=999,
                             created_at=datetime(2026, 1, index, tzinfo=timezone.utc)))
    db.add(StockMovement(product_id=product.id, warehouse_id=warehouse.id, movement_type='IN',
                         quantity=Decimal('2'), unit_cost=Decimal('12.50'),
                         reference_type='GOODS_RECEIPT_RETURN', reference_id=999,
                         created_at=datetime(2026, 1, 4, tzinfo=timezone.utc)))
    db.commit()
    args = dict(product_id=product.id, warehouse_id=warehouse.id, purchase_order_id=None,
                goods_receipt_id=None, location_id=None, department_id=None, account_id=None,
                source_kind='RETURN', date_from=None, date_to=None, search=None, page_size=1, db=db, user=ADMIN)
    first = list_movements(page=1, **args)
    second = list_movements(page=2, **args)
    assert first['total_items'] == 2
    assert first['summary']['out_qty'] == Decimal('4')
    assert first['summary']['out_value'] == Decimal('50')
    assert first['summary']['in_qty'] == 0
    assert first['items'][0]['source_kind'] == second['items'][0]['source_kind'] == 'RETURN'
    assert first['items'][0]['source_label'] == 'Retur supplier'
    assert first['items'][0]['id'] != second['items'][0]['id']
