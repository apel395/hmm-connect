from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.stock_opnames import listing
from app.models import Base
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.stock_movement import StockMovement
from app.models.stock_opname import StockOpname
from app.models.user import User
from app.models.warehouse import Warehouse
from app.schemas.stock_opname import StockOpnameCountItem, StockOpnameCountUpdate, StockOpnameCreate
from app.services.stock_opname_service import StockOpnameService


@pytest.fixture
def stock_db(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    monkeypatch.setattr("app.services.stock_opname_service.validate_dimensions", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.services.stock_opname_service.AuditService.log", lambda *args, **kwargs: None)
    sequence = iter(range(1, 500))
    monkeypatch.setattr("app.services.stock_opname_service.next_document_number", lambda *args: f"SO-{next(sequence):04d}")

    warehouse = Warehouse(code="WH-1", name="Warehouse 1", is_active=True)
    user = User(username="warehouse", email="warehouse@example.test", full_name="Warehouse", password_hash="x", is_active=True)
    products = [
        Product(code="A", name="Product A", group_code="1", group_name="Food", subgroup_code="1-1", subgroup_name="GROCERIES", uom="PCS", usage_uom="PCS", is_active=True),
        Product(code="B", name="Product B", group_code="1", group_name="Food", subgroup_code="1-1", subgroup_name="GROCERIES", uom="KG", usage_uom="KG", is_active=True),
    ]
    db.add_all([warehouse, user, *products]); db.flush()
    inventory = [
        Inventory(warehouse_id=warehouse.id, product_id=products[0].id, quantity=Decimal("20.0000"), average_cost=Decimal("10.0000")),
        Inventory(warehouse_id=warehouse.id, product_id=products[1].id, quantity=Decimal("10.1250"), average_cost=Decimal("4.5000")),
    ]
    db.add_all(inventory); db.commit()
    yield db, warehouse, user, products, inventory
    db.close()


def create_opname(db, warehouse, user):
    return StockOpnameService.create(db=db, data=StockOpnameCreate(warehouse_id=warehouse.id), current_user=user)


def test_create_snapshots_inventory_and_snapshot_is_immutable(stock_db):
    db, warehouse, user, _, inventory = stock_db
    opname = create_opname(db, warehouse, user)
    assert [(item.system_quantity, item.unit_cost) for item in opname.items] == [
        (Decimal("20.0000"), Decimal("10.0000")),
        (Decimal("10.1250"), Decimal("4.5000")),
    ]
    inventory[0].quantity = Decimal("25"); inventory[0].average_cost = Decimal("12"); db.commit(); db.refresh(opname.items[0])
    assert (opname.items[0].system_quantity, opname.items[0].unit_cost) == (Decimal("20.0000"), Decimal("10.0000"))


def test_duplicate_active_rejected_but_terminal_allows_new(stock_db):
    db, warehouse, user, *_ = stock_db
    opname = create_opname(db, warehouse, user)
    with pytest.raises(HTTPException) as duplicate:
        create_opname(db, warehouse, user)
    assert duplicate.value.status_code == 409
    opname.status = "REJECTED"; db.commit()
    assert create_opname(db, warehouse, user).status == "DRAFT"


def test_partial_count_preserves_null_and_distinguishes_zero(stock_db):
    db, warehouse, user, *_ = stock_db
    opname = create_opname(db, warehouse, user)
    StockOpnameService.update_counts(
        db=db, opname_id=opname.id,
        data=StockOpnameCountUpdate(items=[StockOpnameCountItem(item_id=opname.items[0].id, physical_quantity=Decimal("0"))]),
        current_user=user,
    )
    assert opname.items[0].physical_quantity == Decimal("0.0000")
    assert opname.items[1].physical_quantity is None
    with pytest.raises(ValidationError):
        StockOpnameCountItem(item_id=opname.items[0].id, physical_quantity=Decimal("-1"))
    with pytest.raises(HTTPException) as incomplete:
        StockOpnameService.submit(db=db, opname_id=opname.id, current_user=user)
    assert incomplete.value.status_code == 409


@pytest.mark.parametrize(("physical", "movement_type", "variance"), [
    ("24.0000", "IN", Decimal("4.0000")),
    ("17.0000", "OUT", Decimal("-3.0000")),
])
def test_post_variance_preserves_cost_reference_and_dimensions(stock_db, physical, movement_type, variance):
    db, warehouse, user, _, inventory = stock_db
    opname = create_opname(db, warehouse, user)
    opname.status = "APPROVED"
    opname.items[0].physical_quantity = Decimal(physical)
    opname.items[1].physical_quantity = opname.items[1].system_quantity
    db.commit()
    StockOpnameService.post(db=db, opname_id=opname.id, current_user=user)
    movement = db.query(StockMovement).one()
    assert inventory[0].quantity == Decimal(physical)
    assert inventory[0].average_cost == Decimal("10.0000")
    assert (movement.movement_type, movement.quantity, movement.unit_cost) == (movement_type, variance, Decimal("10.0000"))
    assert (movement.reference_type, movement.reference_id, movement.warehouse_id) == ("STOCK_OPNAME", opname.id, warehouse.id)


def test_zero_variance_posts_without_movement_and_duplicate_post_fails(stock_db):
    db, warehouse, user, *_ = stock_db
    opname = create_opname(db, warehouse, user); opname.status = "APPROVED"
    for item in opname.items: item.physical_quantity = item.system_quantity
    db.commit(); StockOpnameService.post(db=db, opname_id=opname.id, current_user=user)
    assert db.query(StockMovement).count() == 0
    with pytest.raises(HTTPException) as duplicate:
        StockOpnameService.post(db=db, opname_id=opname.id, current_user=user)
    assert duplicate.value.status_code == 409


def test_stale_multiline_snapshot_is_atomic(stock_db):
    db, warehouse, user, _, inventory = stock_db
    opname = create_opname(db, warehouse, user); opname.status = "APPROVED"
    opname.items[0].physical_quantity = Decimal("18")
    opname.items[1].physical_quantity = Decimal("9")
    inventory[1].quantity = Decimal("11"); db.commit()
    with pytest.raises(HTTPException) as stale:
        StockOpnameService.post(db=db, opname_id=opname.id, current_user=user)
    assert stale.value.status_code == 409
    db.rollback(); db.refresh(inventory[0])
    assert inventory[0].quantity == Decimal("20.0000")
    assert db.query(StockMovement).count() == 0


def test_decimal_variance_preserved(stock_db):
    db, warehouse, user, *_ = stock_db
    opname = create_opname(db, warehouse, user); opname.status = "APPROVED"
    opname.items[0].physical_quantity = opname.items[0].system_quantity
    opname.items[1].physical_quantity = Decimal("9.8750"); db.commit()
    StockOpnameService.post(db=db, opname_id=opname.id, current_user=user)
    assert db.query(StockMovement).one().quantity == Decimal("-0.2500")


def test_listing_page_three_has_fifteen_rows(stock_db):
    db, warehouse, user, *_ = stock_db
    for index in range(55):
        db.add(StockOpname(opname_number=f"HIST-{index:03d}", status="POSTED", count_date=date(2026, 8, 1), warehouse_id=warehouse.id, created_by_id=user.id))
    db.commit()
    page = listing(page=3, page_size=20, db=db, _=user)
    assert (len(page["items"]), page["total_items"], page["total_pages"]) == (15, 55, 3)
