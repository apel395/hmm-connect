from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.store_requests import list_store_requests, requester_user, warehouse_user
from app.models import Base
from app.models.business_unit import BusinessUnit
from app.models.chart_of_account import ChartOfAccount
from app.models.department import Department
from app.models.inventory import Inventory
from app.models.location import Location
from app.models.product import Product
from app.models.permission import Permission
from app.models.role import Role
from app.models.stock_movement import StockMovement
from app.models.store_request import StoreIssue, StoreIssueItem, StoreRequest, StoreRequestItem
from app.models.user import User
from app.models.warehouse import Warehouse
from app.schemas.store_request import StoreRequestIssueCreate, StoreRequestIssueItem
from app.services.store_request_service import StoreRequestService


@pytest.fixture
def store_db(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    sequence = iter(range(1, 100))
    monkeypatch.setattr(
        "app.services.store_request_service.next_document_number",
        lambda _db, prefix, **_kwargs: f"{prefix}-TEST-{next(sequence):04d}",
    )

    business_unit = BusinessUnit(code="BU-A", name="Business Unit A", is_active=True)
    department = Department(code="DEP-A", name="Department A", is_active=True, business_unit=business_unit)
    location = Location(code="LOC-A", name="Location A", is_active=True, business_unit=business_unit)
    warehouse = Warehouse(code="WH-A", name="Warehouse A", is_active=True, location=location)
    store_request_manage = Permission(code="store_request.manage", description="Store Request Manage")
    requester_role = Role(name="DEPARTMENT", description=None, permissions=[store_request_manage])
    warehouse_role = Role(name="WAREHOUSE", description=None, permissions=[store_request_manage])
    requester = User(
        username="requester", email="requester@example.test", full_name="Requester",
        password_hash="x", is_active=True, department=department, location=location,
        default_business_unit=business_unit, default_department_id=None, default_location_id=None,
        roles=[requester_role],
    )
    store_user = User(
        username="store", email="store@example.test", full_name="Store User",
        password_hash="x", is_active=True, department=department, location=location,
        default_business_unit=business_unit, default_department_id=None, default_location_id=None,
        roles=[warehouse_role],
    )
    inventory_account = ChartOfAccount(
        account_number="100-300-TEST", account_name="Inventory Test", account_type="ASSET",
        normal_balance="DEBIT", account_subtype="INVENTORY", is_posting=True, is_active=True,
    )
    cogs_account = ChartOfAccount(
        account_number="500-100-TEST", account_name="COGS Test", account_type="EXPENSE",
        normal_balance="DEBIT", account_subtype="COGS", is_posting=True, is_active=True,
    )
    db.add_all([inventory_account, cogs_account])
    db.flush()
    products = [
        Product(
            code=f"ITEM-{index}", name=f"Item {index}", group_code="FIX", group_name="Fixture",
            subgroup_code="FIX", subgroup_name="Fixture", uom="EA", usage_uom="EA", conversion=1,
            cost_price=0, selling_price=0, tax_category="NON_TAXABLE", is_taxable=False, tax_rate=0,
            minimum_stock=0, reorder_level=0, maximum_stock=0, lead_time_days=0,
            is_market_item=False, is_active=True,
            inventory_account_id=inventory_account.id, cogs_account_id=cogs_account.id,
        )
        for index in (1, 2)
    ]
    db.add_all([business_unit, department, location, warehouse, requester, store_user, *products])
    db.flush()
    yield db, business_unit, department, location, warehouse, requester, store_user, products
    db.close()


def make_request(db, business_unit, department, location, warehouse, requester, products, quantities):
    request = StoreRequest(
        sr_number=f"SR-TEST-{len(db.query(StoreRequest).all()) + 1:04d}", status="APPROVED",
        business_unit_id=business_unit.id, department_id=department.id, location_id=location.id,
        warehouse_id=warehouse.id, requested_by_id=requester.id,
    )
    request.items = [
        StoreRequestItem(product_id=product.id, requested_quantity=quantity, issued_quantity=0, uom=product.uom)
        for product, quantity in zip(products, quantities)
    ]
    db.add(request)
    db.commit()
    return request


def test_issue_authorization_and_positive_quantity_validation(store_db):
    _, _, _, _, _, requester, store_user, _ = store_db
    assert requester_user(current_user=requester) is requester
    assert warehouse_user(current_user=requester) is requester
    assert warehouse_user(current_user=store_user) is store_user
    for quantity in (0, -1):
        with pytest.raises(ValidationError):
            StoreRequestIssueItem(item_id=1, quantity=quantity)


def test_partial_issue_exactly_once_and_traceability(store_db):
    db, bu, department, location, warehouse, requester, store_user, products = store_db
    request = make_request(db, bu, department, location, warehouse, requester, products[:1], [20])
    db.add(Inventory(product_id=products[0].id, warehouse_id=warehouse.id, quantity=50, average_cost=10))
    db.commit()

    first = StoreRequestService.create_issue(
        db, request_id=request.id,
        data=StoreRequestIssueCreate(items=[StoreRequestIssueItem(item_id=request.items[0].id, quantity=12)]),
        current_user=store_user,
    )
    assert db.query(Inventory).one().quantity == Decimal("50")
    assert request.items[0].issued_quantity == Decimal("0")

    StoreRequestService.post_issue(db, issue_id=first.id, current_user=store_user)
    assert db.query(Inventory).one().quantity == Decimal("38")
    assert db.query(Inventory).one().average_cost == Decimal("10")
    assert request.items[0].issued_quantity == Decimal("12")
    assert request.status == "PARTIALLY_ISSUED"
    movement = db.query(StockMovement).one()
    assert (movement.movement_type, movement.quantity, movement.unit_cost) == ("OUT", Decimal("-12"), Decimal("10"))
    assert (movement.business_unit_id, movement.department_id, movement.location_id) == (bu.id, department.id, location.id)
    assert (movement.reference_type, movement.reference_id) == ("STORE_REQUEST", request.id)

    with pytest.raises(HTTPException) as duplicate:
        StoreRequestService.post_issue(db, issue_id=first.id, current_user=store_user)
    assert duplicate.value.status_code == 409
    assert db.query(Inventory).one().quantity == Decimal("38")
    assert db.query(StockMovement).count() == 1

    second = StoreRequestService.create_issue(
        db, request_id=request.id,
        data=StoreRequestIssueCreate(items=[StoreRequestIssueItem(item_id=request.items[0].id, quantity=8)]),
        current_user=store_user,
    )
    StoreRequestService.post_issue(db, issue_id=second.id, current_user=store_user)
    assert db.query(Inventory).one().quantity == Decimal("30")
    assert db.query(Inventory).one().average_cost == Decimal("10")
    assert request.items[0].issued_quantity == Decimal("20")
    assert request.status == "ISSUED"
    assert db.query(StockMovement).count() == 2


def test_multiline_failure_does_not_mutate_an_earlier_line(store_db):
    db, bu, department, location, warehouse, requester, store_user, products = store_db
    request = make_request(db, bu, department, location, warehouse, requester, products, [3, 4])
    inventories = [
        Inventory(product_id=products[0].id, warehouse_id=warehouse.id, quantity=10, average_cost=5),
        Inventory(product_id=products[1].id, warehouse_id=warehouse.id, quantity=2, average_cost=7),
    ]
    issue = StoreIssue(issue_number="SI-ATOMIC", store_request_id=request.id, status="DRAFT", created_by_id=store_user.id)
    issue.items = [
        StoreIssueItem(store_request_item_id=request.items[0].id, product_id=products[0].id, quantity=3),
        StoreIssueItem(store_request_item_id=request.items[1].id, product_id=products[1].id, quantity=4),
    ]
    db.add_all([*inventories, issue])
    db.commit()

    with pytest.raises(HTTPException) as error:
        StoreRequestService.post_issue(db, issue_id=issue.id, current_user=store_user)
    assert error.value.status_code == 409
    assert inventories[0].quantity == Decimal("10")
    assert request.items[0].issued_quantity == Decimal("0")
    assert db.query(StockMovement).count() == 0
    assert issue.status == "DRAFT"


def test_store_request_list_paginates_beyond_two_pages(store_db):
    db, bu, department, location, warehouse, requester, _, _ = store_db
    for index in range(55):
        db.add(StoreRequest(
            sr_number=f"SR-PAGE-{index:04d}", status="DRAFT",
            business_unit_id=bu.id, department_id=department.id, location_id=location.id,
            warehouse_id=warehouse.id, requested_by_id=requester.id,
        ))
    db.commit()

    result = list_store_requests(
        status=None, search=None, page=3, page_size=25, db=db, _=requester,
    )
    assert [row["sr_number"] for row in result["items"]] == [
        "SR-PAGE-0004", "SR-PAGE-0003", "SR-PAGE-0002", "SR-PAGE-0001", "SR-PAGE-0000",
    ]
    assert result | {"items": None, "summary": None} == {
        "items": None, "page": 3, "page_size": 25, "total_items": 55,
        "total_pages": 3, "has_next": False, "has_previous": True, "summary": None,
    }


def test_issue_rejects_legacy_empty_store_request(store_db):
    db, bu, department, location, warehouse, requester, store_user, _ = store_db
    request = StoreRequest(
        sr_number="SR-EMPTY",
        status="APPROVED",
        business_unit_id=bu.id,
        department_id=department.id,
        location_id=location.id,
        warehouse_id=warehouse.id,
        requested_by_id=requester.id,
    )
    db.add(request)
    db.commit()

    with pytest.raises(HTTPException) as error:
        StoreRequestService.create_issue(
            db,
            request_id=request.id,
            data=StoreRequestIssueCreate(items=[StoreRequestIssueItem(item_id=999, quantity=1)]),
            current_user=store_user,
        )

    assert error.value.status_code == 409
    assert "at least one item" in str(error.value.detail)
