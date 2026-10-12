from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.stock_opnames import listing
from app.models import Base
from app.models.fiscal_period import FiscalPeriod
from app.models.chart_of_account import ChartOfAccount
from app.models.journal_entry import JournalEntry
from app.models.general_ledger import GeneralLedger
from app.models.business_unit import BusinessUnit
from app.models.inventory import Inventory
from app.models.department import Department
from app.models.location_department import LocationDepartment
from app.models.location import Location
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
    monkeypatch.setattr("app.services.stock_opname_service.next_document_number", lambda *args, **kwargs: f"SO-{next(sequence):04d}")

    business_unit = BusinessUnit(code="BU-1", name="Business Unit 1", is_active=True)
    db.add(business_unit)
    db.flush()
    location = Location(
        code="LOC-1",
        name="Location 1",
        location_type="HOTEL",
        is_active=True,
        business_unit_id=business_unit.id,
    )
    db.add(location)
    db.flush()

    department=Department(code="OPS",name="Operations",business_unit_id=business_unit.id,is_active=True)
    db.add(department);db.flush()
    db.add(LocationDepartment(location_id=location.id,department_id=department.id))
    warehouse = Warehouse(code="WH-1", name="Warehouse 1", is_active=True, location_id=location.id)
    user = User(
        username="warehouse",
        email="warehouse@example.test",
        full_name="Warehouse",
        password_hash="x",
        is_active=True,
        location_id=location.id,
        default_location_id=location.id,
        default_business_unit_id=business_unit.id,
        default_department_id=department.id,
    )
    products = [
        Product(code="A", name="Product A", group_code="1", group_name="Food", subgroup_code="1-1", subgroup_name="GROCERIES", uom="PCS", usage_uom="PCS", is_active=True),
        Product(code="B", name="Product B", group_code="1", group_name="Food", subgroup_code="1-1", subgroup_name="GROCERIES", uom="KG", usage_uom="KG", is_active=True),
    ]
    db.add_all([warehouse, user, *products]); db.flush()
    today = date.today()
    from calendar import monthrange
    db.add(FiscalPeriod(fiscal_year=today.year,fiscal_month=today.month,period_name='Test open period',
        start_date=today.replace(day=1),end_date=today.replace(day=monthrange(today.year,today.month)[1]),
        is_open=True,is_closed=False,allow_backdated_entries=True))
    inv_coa=ChartOfAccount(account_number='100-300-100',account_name='Inventory',account_type='ASSET',normal_balance='DEBIT',is_posting=True)
    cogs=ChartOfAccount(account_number='500-100-100',account_name='HPP',account_type='EXPENSE',normal_balance='DEBIT',is_posting=True)
    db.add_all([inv_coa,cogs]);db.flush()
    for product in products:
        product.inventory_account_id=inv_coa.id
        product.cogs_account_id=cogs.id

    inventory = [
        Inventory(warehouse_id=warehouse.id, product_id=products[0].id, quantity=Decimal("20.0000"), average_cost=Decimal("10.0000")),
        Inventory(warehouse_id=warehouse.id, product_id=products[1].id, quantity=Decimal("10.1250"), average_cost=Decimal("4.5000")),
    ]
    db.add_all(inventory); db.commit()
    yield db, warehouse, user, products, inventory
    db.close()


def create_opname(db, warehouse, user):
    return StockOpnameService.create(db=db, data=StockOpnameCreate(warehouse_id=warehouse.id, department_id=user.default_department_id), current_user=user)


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
    assert movement.business_unit_id == opname.business_unit_id
    assert movement.location_id == opname.location_id


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
        db.add(StockOpname(opname_number=f"HIST-{index:03d}", status="POSTED", count_date=date(2026, 8, 1), warehouse_id=warehouse.id, location_id=user.location_id, business_unit_id=user.default_business_unit_id, created_by_id=user.id))
    db.commit()
    page = listing(page=3, page_size=20, db=db, _=user)
    assert (len(page["items"]), page["total_items"], page["total_pages"]) == (15, 55, 3)


def test_listing_is_restricted_to_user_work_location(stock_db):
    db, warehouse, user, *_ = stock_db
    own = StockOpname(
        opname_number="OWN-LOCATION",
        status="POSTED",
        count_date=date(2026, 8, 1),
        warehouse_id=warehouse.id,
        location_id=user.location_id,
        business_unit_id=user.default_business_unit_id,
        created_by_id=user.id,
    )
    other_location = Location(
        code="LOC-2",
        name="Location 2",
        location_type="HOTEL",
        is_active=True,
        business_unit_id=user.default_business_unit_id,
    )
    db.add_all([own, other_location])
    db.flush()
    db.add(
        StockOpname(
            opname_number="OTHER-LOCATION",
            status="POSTED",
            count_date=date(2026, 8, 1),
            warehouse_id=warehouse.id,
            location_id=other_location.id,
            business_unit_id=user.default_business_unit_id,
            created_by_id=user.id,
        )
    )
    db.commit()

    page = listing(page=1, page_size=25, db=db, _=user)

    assert [row["opname_number"] for row in page["items"]] == ["OWN-LOCATION"]
    assert page["total_items"] == 1


def test_create_rejects_empty_inventory_snapshot(stock_db):
    db, warehouse, user, _, inventory = stock_db
    for row in inventory:
        db.delete(row)
    db.commit()

    with pytest.raises(HTTPException) as error:
        create_opname(db, warehouse, user)

    assert error.value.status_code == 409
    assert error.value.detail["code"] == "EMPTY_STOCK_SNAPSHOT"


def test_create_rejects_warehouse_location_mismatch(stock_db):
    db, warehouse, user, *_ = stock_db
    other = Location(
        code="LOC-MISMATCH",
        name="Location Mismatch",
        location_type="HOTEL",
        is_active=True,
        business_unit_id=user.default_business_unit_id,
    )
    db.add(other)
    db.commit()

    with pytest.raises(HTTPException) as error:
        StockOpnameService.create(
            db=db,
            data=StockOpnameCreate(warehouse_id=warehouse.id, location_id=other.id, department_id=user.default_department_id),
            current_user=user,
        )

    assert error.value.status_code == 422
    assert "belongs to Location" in str(error.value.detail)


def test_stock_count_posts_gl_and_unpost_reuses_source_journal(stock_db):
    db, warehouse, user, _, inventory = stock_db
    op=create_opname(db,warehouse,user);op.status='APPROVED'
    for item in op.items:item.physical_quantity=item.system_quantity
    op.items[0].physical_quantity=Decimal('17')
    db.commit()
    StockOpnameService.post(db=db,opname_id=op.id,current_user=user)
    journal=db.query(JournalEntry).one()
    assert journal.status=='POSTED'
    assert sum(line.debit for line in journal.lines)==sum(line.credit for line in journal.lines)==30
    assert db.query(GeneralLedger).count()==2
    StockOpnameService.unpost(db=db,opname_id=op.id,current_user=user)
    assert inventory[0].quantity==20
    assert db.query(GeneralLedger).count()==0
    assert journal.status=='DRAFT'
    StockOpnameService.post(db=db,opname_id=op.id,current_user=user)
    assert db.query(JournalEntry).count()==1
    assert db.query(GeneralLedger).count()==2


def test_closed_period_count_changes_neither_stock_nor_accounting(stock_db):
    db,warehouse,user,_,inventory=stock_db
    op=create_opname(db,warehouse,user);op.status='APPROVED'
    for item in op.items:item.physical_quantity=item.system_quantity
    op.items[0].physical_quantity=19
    db.query(FiscalPeriod).one().is_closed=True
    db.commit()
    with pytest.raises(HTTPException):StockOpnameService.post(db=db,opname_id=op.id,current_user=user)
    db.rollback()
    assert inventory[0].quantity==20
    assert db.query(StockMovement).count()==db.query(JournalEntry).count()==db.query(GeneralLedger).count()==0


def test_location_count_payload_contains_no_system_values(stock_db):
    from app.api.v1.stock_opnames import _detail
    db,warehouse,user,*_=stock_db
    op=create_opname(db,warehouse,user)
    data=_detail(db,op,user)
    assert data['blind_count'] is True
    assert data['total_variance_quantity'] is None
    for row in data['items']:
        assert not {'system_quantity','variance_quantity','variance_value','unit_cost'} & row.keys()


def test_store_issue_posts_stock_and_gl_once(stock_db):
    from app.models.store_request import StoreRequest,StoreRequestItem,StoreIssue,StoreIssueItem
    from app.services.store_request_service import StoreRequestService
    db,warehouse,user,products,inventory=stock_db
    request=StoreRequest(sr_number='SR-TEST',status='APPROVED',request_date=date.today(),
        warehouse_id=warehouse.id,business_unit_id=user.default_business_unit_id,
        location_id=user.location_id,department_id=user.default_department_id,requested_by_id=user.id)
    request.items=[StoreRequestItem(product_id=products[0].id,requested_quantity=3,issued_quantity=0,uom='PCS')]
    db.add(request);db.flush()
    issue=StoreIssue(issue_number='SI-TEST',store_request_id=request.id,status='DRAFT',issue_date=date.today(),created_by_id=user.id)
    issue.items=[StoreIssueItem(store_request_item_id=request.items[0].id,product_id=products[0].id,quantity=3)]
    db.add(issue);db.commit()
    StoreRequestService.post_issue(db,issue_id=issue.id,current_user=user)
    assert inventory[0].quantity==17
    assert db.query(JournalEntry).one().status=='POSTED'
    assert db.query(GeneralLedger).count()==2
    with pytest.raises(HTTPException):StoreRequestService.post_issue(db,issue_id=issue.id,current_user=user)
    db.rollback()
    assert inventory[0].quantity==17
    assert db.query(GeneralLedger).count()==2


def test_multi_item_remaining_quantities_ignore_visible_event_filter(stock_db):
    from datetime import datetime,timezone
    from app.api.v1.inventory import list_movements
    db,warehouse,user,products,_=stock_db
    for product,kind,amount in [(products[0],'IN',5),(products[0],'OUT',2),(products[1],'IN',2)]:
        db.add(StockMovement(product_id=product.id,warehouse_id=warehouse.id,movement_type=kind,quantity=amount,unit_cost=10,
            reference_type='STOCK_ADJUSTMENT',reference_id=1,created_at=datetime(2026,10,1,tzinfo=timezone.utc)))
    db.commit()
    data=list_movements(db=db,user=user,page=1,page_size=50,search=None)
    a=sorted([row for row in data['items'] if row['product_id']==products[0].id],key=lambda r:r['id'])
    assert [row['running_quantity'] for row in a]==[22,20]
    b=[row for row in data['items'] if row['product_id']==products[1].id]
    assert b[0]['running_quantity']==Decimal('10.1250')


def test_market_list_receiving_reserves_source_and_does_not_create_po(stock_db):
    from app.models.market_list import MarketList,MarketListItem
    from app.models.supplier import Supplier
    from app.models.role import Role
    from app.models.purchase_order import PurchaseOrder
    from app.schemas.goods_receipt import GoodsReceiptCreate
    from app.services.goods_receipt_service import GoodsReceiptService
    from app.services.market_list_receiving import allocated_market_items
    db,warehouse,user,products,_=stock_db
    user.roles=[Role(name='SYSTEM_ADMINISTRATOR')]
    products[0].inventory_treatment='STOCK';products[0].tax_category='NON_TAXABLE';products[0].subgroup_name='VEGETABLES';products[0].subgroup_code='1-5'
    supplier=Supplier(code='S1',name='Supplier',is_active=True)
    market=MarketList(ml_number='ML-TEST',status='APPROVED',business_unit_id=user.default_business_unit_id,
        location_id=user.location_id,department_id=user.default_department_id)
    market.items=[MarketListItem(product_id=products[0].id,quantity=10,estimated_price=10,total_price=100)]
    db.add_all([market,supplier]);db.commit()
    def payload(quantity):
        return GoodsReceiptCreate(market_list_id=market.id,supplier_id=supplier.id,
            business_unit_id=user.default_business_unit_id,location_id=user.location_id,department_id=user.default_department_id,
            warehouse_id=warehouse.id,destination_type='WAREHOUSE',items=[dict(market_list_item_id=market.items[0].id,product_id=products[0].id,quantity=quantity,unit_cost=10)])
    receipt=GoodsReceiptService.create(db,data=payload(6),user=user)
    db.commit()
    assert receipt.market_list_id==market.id and receipt.purchase_order_id is None
    assert db.query(PurchaseOrder).count()==0
    assert allocated_market_items(db,market.id)[market.items[0].id]==6
    with pytest.raises(HTTPException):GoodsReceiptService.create(db,data=payload(5),user=user)
    db.rollback()
    assert allocated_market_items(db,market.id)[market.items[0].id]==6
    from app.services.market_list_service import MarketListService
    from app.schemas.market_list import MarketListConvertCreate
    order=MarketListService.convert_to_purchase_order(db,market_list_id=market.id,
        data=MarketListConvertCreate(supplier_id=supplier.id),current_user=user)
    assert order.items[0].quantity==4
    assert allocated_market_items(db,market.id)[market.items[0].id]==10


def test_print_counts_only_requests_and_is_idempotent(stock_db,monkeypatch):
    from app.services.document_print_tracking import record_print
    from app.models.role import Role
    db,warehouse,user,*_=stock_db
    op=create_opname(db,warehouse,user)
    monkeypatch.undo()
    user.roles=[Role(name='SYSTEM_ADMINISTRATOR')];db.commit()
    first=record_print(db,user,'STOCK_OPNAME',op.id,'one')
    replay=record_print(db,user,'STOCK_OPNAME',op.id,'one')
    second=record_print(db,user,'STOCK_OPNAME',op.id,'two')
    assert first['print_count']==replay['print_count']==1
    assert second['print_count']==2 and second['reprint_number']==1
    assert db.query(StockMovement).count()==0


def test_failed_document_archive_restore_preserves_no_transactions(stock_db,monkeypatch):
    from app.models.market_list import MarketList
    from app.models.role import Role
    from app.services.purchasing_exceptions import archive_document,unfinished_documents
    db,_,user,*_=stock_db
    monkeypatch.undo()
    user.roles=[Role(name='SYSTEM_ADMINISTRATOR')]
    market=MarketList(ml_number='ML-FAILED',status='REJECTED',business_unit_id=user.default_business_unit_id,
        location_id=user.location_id,department_id=user.default_department_id)
    db.add(market);db.commit()
    archive_document(db,user,'MARKET_LIST',market.id,'Supplier cancelled')
    assert market.status=='ARCHIVED'
    assert [row['number'] for row in unfinished_documents(db,user,archived=True)]==['ML-FAILED']
    archive_document(db,user,'MARKET_LIST',market.id,'Restore for review',restore=True)
    assert market.status=='REJECTED'
    assert db.query(JournalEntry).count()==db.query(StockMovement).count()==0


def test_receiving_live_date_is_stamped_at_submission_and_2025_stays_excluded(stock_db,monkeypatch):
    from datetime import datetime,timezone
    from app.models.role import Role
    from app.models.supplier import Supplier
    from app.schemas.goods_receipt import GoodsReceiptCreate
    from app.services.goods_receipt_service import GoodsReceiptService
    from app.api.v1 import goods_receipts
    db,warehouse,user,products,_=stock_db
    user.roles=[Role(name='SYSTEM_ADMINISTRATOR')]
    products[0].tax_category='NON_TAXABLE';products[0].inventory_treatment='STOCK'
    supplier=Supplier(code='DATE-S',name='Supplier',is_active=True);db.add(supplier);db.commit()
    payload=dict(supplier_id=supplier.id,business_unit_id=user.default_business_unit_id,location_id=user.location_id,
        department_id=user.default_department_id,warehouse_id=warehouse.id,items=[dict(product_id=products[0].id,quantity=1,unit_cost=10)])
    receipt=GoodsReceiptService.create(db,user=user,data=GoodsReceiptCreate(**payload,received_at=datetime(2026,1,1,tzinfo=timezone.utc)))
    assert GoodsReceiptService.business_date(receipt.received_at)==date.today()
    db.commit()
    before=receipt.received_at
    frozen=before.replace(hour=11,minute=12,second=13,microsecond=0)
    class Clock:
        @staticmethod
        def now(tz):return frozen
    monkeypatch.setattr(goods_receipts,'datetime',Clock)
    monkeypatch.setattr(goods_receipts,'start_approval',lambda *a,**kw:None)
    goods_receipts.submit_receipt(receipt.id,db,user)
    assert receipt.received_at==frozen
    assert db.query(StockMovement).count()==0
    with pytest.raises(HTTPException):
        GoodsReceiptService.create(db,user=user,data=GoodsReceiptCreate(**payload,source_type='HISTORICAL_ENTRY',received_at=datetime(2025,12,1,tzinfo=timezone.utc)))


def test_po_date_cannot_precede_pr_and_receiving_uses_jakarta_day():
    from types import SimpleNamespace
    from datetime import datetime,timezone
    from app.services.purchase_order_service import PurchaseOrderService
    from app.services.goods_receipt_service import GoodsReceiptService
    with pytest.raises(HTTPException):
        PurchaseOrderService._validate_source_dates(date(2026,1,5),[SimpleNamespace(request_date=date(2026,1,6))])
    PurchaseOrderService._validate_source_dates(date(2026,1,6),[SimpleNamespace(request_date=date(2026,1,6))])
    assert GoodsReceiptService.business_date(datetime(2025,12,31,18,tzinfo=timezone.utc))==date(2026,1,1)
