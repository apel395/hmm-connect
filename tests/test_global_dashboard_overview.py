from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.dashboard import overview
from app.models import Base
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_requisition import PurchaseRequisition
from app.models.supplier import Supplier
from app.models.warehouse import Warehouse


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()
    engine.dispose()


def test_overview_uses_full_location_scope_and_hides_ungranted_sections(db):
    supplier = Supplier(code="SUP-DASH", name="Dashboard Supplier", is_active=True)
    product = Product(
        code="DASH-P", name="Dashboard Product", group_code="1", group_name="Food",
        subgroup_code="1", subgroup_name="Food", uom="PCS", usage_uom="PCS",
        is_active=True, minimum_stock=Decimal("10"),
    )
    warehouses = [
        Warehouse(code="DASH-W1", name="One", location_id=1, is_active=True),
        Warehouse(code="DASH-W2", name="Two", location_id=2, is_active=True),
    ]
    db.add_all([supplier, product, *warehouses])
    db.flush()
    for index in range(27):
        db.add(PurchaseRequisition(
            pr_number=f"DASH-PR-{index}", status="PENDING_APPROVAL", location_id=1,
        ))
    db.add(PurchaseRequisition(
        pr_number="DASH-OTHER", status="PENDING_APPROVAL", location_id=2,
    ))
    db.add_all([
        PurchaseOrder(po_number="DASH-PO-1", supplier_id=supplier.id, location_id=1, status="APPROVED"),
        PurchaseOrder(po_number="DASH-PO-2", supplier_id=supplier.id, location_id=2, status="APPROVED"),
        Inventory(product_id=product.id, warehouse_id=warehouses[0].id,
                  quantity=Decimal("4"), average_cost=Decimal("20")),
        Inventory(product_id=product.id, warehouse_id=warehouses[1].id,
                  quantity=Decimal("20"), average_cost=Decimal("20")),
    ])
    db.commit()
    scoped_admin = SimpleNamespace(
        roles=[SimpleNamespace(name="SYSTEM_ADMINISTRATOR")],
        default_location_id=None, location_id=None,
    )
    all_locations = overview(db=db, user=scoped_admin)
    assert all_locations["purchasing"]["pr_waiting"] == 28
    assert all_locations["inventory"]["stock_value"] == "480.00"

    permission = lambda code: SimpleNamespace(code=code)
    user = SimpleNamespace(
        roles=[SimpleNamespace(name="PURCHASER", permissions=[
            permission("pr.view"), permission("po.view"), permission("inventory.view"),
        ])],
        default_location_id=1, location_id=2,
    )
    result = overview(db=db, user=user)
    assert result["scope"]["location_id"] == 1
    assert result["purchasing"]["pr_waiting"] == 27
    assert result["purchasing"]["po_open"] == 1
    assert len(result["purchasing"]["recent_orders"]) == 1
    assert "rr_waiting" not in result["purchasing"]
    assert result["inventory"]["reorder_required"] == 1
    assert result["inventory"]["stock_value"] == "80.00"
    assert result["finance"] is None
