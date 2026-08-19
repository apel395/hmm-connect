import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.products import classification_master
from app.api.v1.roles import (
    CORE_ROLE_PERMISSIONS,
    RoleInput,
    create_role,
    delete_role,
    list_permissions,
    list_roles,
    require_admin,
    update_role,
)
from app.api.v1.suppliers import router as supplier_router
from app.api.v1.suppliers import update_supplier
from app.models import Base
from app.models.item_group import ItemGroup
from app.models.item_subgroup import ItemSubgroup
from app.models.permission import Permission
from app.models.role import Role
from app.models.supplier import Supplier
from app.models.user import User
from app.schemas.supplier import SupplierUpdate


@pytest.fixture
def master_db(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = factory()
    monkeypatch.setattr("app.api.v1.roles.record_audit", lambda *args, **kwargs: None)
    admin_role = Role(name="SYSTEM_ADMINISTRATOR", description="Administrator")
    admin = User(
        username="admin", email="admin@example.test", full_name="Admin", password_hash="x",
        is_active=True, roles=[admin_role],
    )
    db.add(admin)
    db.commit()
    yield db, factory, admin
    db.close()


def test_supplier_patch_put_persistence_and_missing(master_db):
    db, _, admin = master_db
    supplier = Supplier(code="SUP-TEST", name="Original", is_pkp=False, is_active=True)
    db.add(supplier)
    db.commit()

    updated = update_supplier(
        supplier.id,
        SupplierUpdate(name="Edited", address="New address", bank_name="Bank", is_pkp=True, is_active=False),
        db=db,
        _=admin,
    )
    db.expire_all()
    persisted = db.get(Supplier, supplier.id)
    assert (updated.name, persisted.address, persisted.bank_name) == ("Edited", "New address", "Bank")
    assert persisted.is_pkp is True and persisted.is_active is False

    update_supplier(supplier.id, SupplierUpdate(name="PUT compatible"), db=db, _=admin)
    assert db.get(Supplier, supplier.id).name == "PUT compatible"
    methods = {method for route in supplier_router.routes if route.path.endswith("/{supplier_id}") for method in route.methods}
    assert {"PATCH", "PUT"}.issubset(methods)

    with pytest.raises(HTTPException) as missing:
        update_supplier(999999, SupplierUpdate(name="Missing"), db=db, _=admin)
    assert missing.value.status_code == 404


def test_classification_master_is_independent_of_product_rows(master_db):
    db, _, admin = master_db
    food = ItemGroup(code="FOOD", name="Food", is_active=True)
    beverage = ItemGroup(code="BEVERAGE", name="Beverage", is_active=True)
    inactive = ItemGroup(code="HIDDEN", name="Hidden", is_active=False)
    food.subgroups = [
        ItemSubgroup(code="1-1", name="Meat", is_active=True),
        ItemSubgroup(code="1-10", name="Dairy", is_active=True),
        ItemSubgroup(code="1-X", name="Inactive", is_active=False),
    ]
    beverage.subgroups = [ItemSubgroup(code="2-1", name="Water", is_active=True)]
    inactive.subgroups = [ItemSubgroup(code="X-1", name="Hidden", is_active=True)]
    db.add_all([food, beverage, inactive])
    db.commit()

    result = classification_master(db=db, _=admin)
    assert [group["code"] for group in result] == ["BEVERAGE", "FOOD"]
    food_result = next(group for group in result if group["code"] == "FOOD")
    assert [(item["code"], item["name"]) for item in food_result["subgroups"]] == [
        ("1-1", "Meat"), ("1-10", "Dairy"),
    ]


def test_core_role_changes_survive_reads_and_new_session(master_db):
    db, factory, admin = master_db
    dashboard = Permission(code="dashboard.view", description="Dashboard")
    added = Permission(code="reports.view", description="Reports")
    purchasing = Role(name="PURCHASING", description="Custom description", permissions=[dashboard])
    db.add_all([added, purchasing])
    db.commit()

    update_role(
        purchasing.id,
        RoleInput(name="PURCHASING", description=None, permission_codes=["reports.view"]),
        db=db,
        user=admin,
    )
    list_roles(db=db, _=admin)
    list_permissions(db=db, _=admin)
    list_roles(db=db, _=admin)
    db.close()

    fresh = factory()
    role = fresh.query(Role).filter(Role.name == "PURCHASING").one()
    assert role.description is None
    assert {permission.code for permission in role.permissions} == {"reports.view"}
    fresh.close()


def test_role_guards_validation_and_custom_lifecycle(master_db):
    db, _, admin = master_db
    db.add_all([
        Permission(code="dashboard.view", description="Dashboard"),
        Permission(code="reports.view", description="Reports"),
    ])
    purchasing = Role(name="PURCHASING", description="Purchasing")
    warehouse = Role(name="WAREHOUSE", description="Warehouse")
    assigned = Role(name="ASSIGNED", description="Assigned")
    assigned_user = User(
        username="assigned", email="assigned@example.test", full_name="Assigned", password_hash="x",
        is_active=True, roles=[assigned],
    )
    db.add_all([purchasing, warehouse, assigned_user])
    db.commit()

    with pytest.raises(HTTPException) as renamed:
        update_role(purchasing.id, RoleInput(name="BUYER", permission_codes=[]), db=db, user=admin)
    assert renamed.value.status_code == 409
    list_roles(db=db, _=admin)
    core_roles = db.query(Role).filter(Role.name.in_(CORE_ROLE_PERMISSIONS)).all()
    assert {role.name for role in core_roles} == set(CORE_ROLE_PERMISSIONS)
    for role in core_roles:
        with pytest.raises(HTTPException) as deleted:
            delete_role(role.id, db=db, user=admin)
        assert deleted.value.status_code == 409
    with pytest.raises(HTTPException):
        delete_role(assigned.id, db=db, user=admin)

    custom = create_role(
        RoleInput(name="Finance Assistant", description="Custom", permission_codes=["dashboard.view", "dashboard.view"]),
        db=db,
        user=admin,
    )
    assert custom["name"] == "FINANCE_ASSISTANT"
    assert [permission["code"] for permission in custom["permissions"]] == ["dashboard.view"]
    custom_id = custom["id"]

    with pytest.raises(HTTPException) as invalid:
        update_role(
            custom_id,
            RoleInput(name="Finance Assistant", description="Changed", permission_codes=["reports.view", "made.up.permission"]),
            db=db,
            user=admin,
        )
    assert invalid.value.status_code == 400
    db.expire_all()
    unchanged = db.get(Role, custom_id)
    assert unchanged.description == "Custom"
    assert {permission.code for permission in unchanged.permissions} == {"dashboard.view"}
    assert db.query(Permission).filter(Permission.code == "made.up.permission").count() == 0

    update_role(
        custom_id,
        RoleInput(name="Finance Helper", description="Updated", permission_codes=["reports.view"]),
        db=db,
        user=admin,
    )
    assert db.get(Role, custom_id).name == "FINANCE_HELPER"
    delete_role(custom_id, db=db, user=admin)
    assert db.get(Role, custom_id) is None

    non_admin = User(username="plain", email="plain@example.test", full_name="Plain", password_hash="x", is_active=True)
    with pytest.raises(HTTPException) as forbidden:
        require_admin(non_admin)
    assert forbidden.value.status_code == 403
    assert set(CORE_ROLE_PERMISSIONS) >= {"SYSTEM_ADMINISTRATOR", "PURCHASING", "WAREHOUSE"}
