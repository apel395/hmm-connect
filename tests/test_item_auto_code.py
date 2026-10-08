import re
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.models import Base
from app.models.item_group import ItemGroup
from app.models.item_subgroup import ItemSubgroup
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductUpdate
from app.api.v1.products import create_product, preview_item_code, update_product
from app.services.item_code import lock_item_creation, next_item_code

ADMIN = SimpleNamespace(roles=[SimpleNamespace(name="SYSTEM_ADMINISTRATOR")])


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    @event.listens_for(engine, "connect")
    def sqlite_regex(connection, _):
        connection.create_function("regexp_replace", 4, lambda value, pattern, replacement, flags: re.sub(pattern, replacement, value or ""))
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        group = ItemGroup(code="1", name="FOOD", item_type="BUY", is_active=True)
        group.subgroups = [ItemSubgroup(code="1-1", name="MEAT", is_active=True), ItemSubgroup(code="1-10", name="OTHER", is_active=True)]
        session.add(group); session.commit()
        yield session
    engine.dispose()


def payload(name="Kambing Guling", **overrides):
    return ProductCreate(name=name, group_code="1", group_name="FOOD", subgroup_code="1-1", subgroup_name="MEAT", uom="Tray", usage_uom="Portion", **overrides)


def test_preview_is_read_only_and_save_recomputes_stale_code(db):
    first = preview_item_code("1", "1-1", "BUY", db, ADMIN)["code"]
    assert first == "1-100001"
    assert preview_item_code("1", "1-1", "BUY", db, ADMIN)["code"] == first
    assert db.query(Product).count() == 0
    a = create_product(payload(code=first, auto_code=True), db, ADMIN)
    b = create_product(payload("Daging Kambing", code=first, auto_code=True), db, ADMIN)
    assert a.code == "1-100001" and b.code == "1-100002"
    assert a.uom == "Tray" and a.usage_uom == "Portion"
    update_product(a.id, ProductUpdate(uom="Bucket", usage_uom="Serving"), db, ADMIN)
    assert a.code == "1-100001" and a.uom == "Bucket" and a.usage_uom == "Serving"


def test_inactive_and_manual_items_reserve_numbers_and_other_subgroup_does_not(db):
    create_product(payload(code="1-100009", is_active=False), db, ADMIN)
    create_product(payload("Other", code="1-1000045"), db, ADMIN)
    assert next_item_code(db, "1", "1-1") == "1-100010"
    assert next_item_code(db, "1", "1-10") == "1-1000046"


@pytest.mark.parametrize("kind, subgroup", [("SELL", "1-1"), ("BUY", "2-1"), ("BUY", "")])
def test_preview_rejects_wrong_classification(db, kind, subgroup):
    with pytest.raises(HTTPException) as error:
        preview_item_code("1", subgroup, kind, db, ADMIN)
    assert error.value.status_code == 422


def test_sell_catalog_uses_separate_prefix(db):
    group = ItemGroup(code="S", name="FOOD SERVICE", item_type="SELL", is_active=True)
    group.subgroups = [ItemSubgroup(code="S-1", name="MENU", is_active=True)]
    db.add(group); db.commit()
    assert preview_item_code("S", "S-1", "SELL", db, ADMIN)["code"] == "S-100001"


def test_postgres_creation_lock_is_transaction_scoped():
    calls = []
    fake = SimpleNamespace(get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name="postgresql")), execute=lambda statement: calls.append(str(statement)))
    lock_item_creation(fake)
    assert calls == ["SELECT pg_advisory_xact_lock(hashtext('MMH_ITEM_CODE'))"]
