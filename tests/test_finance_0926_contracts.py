from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.chart_of_account import ChartOfAccount
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.supplier import Supplier
from app.models.product import Product
from app.models.warehouse import Warehouse
from app.models.inventory import Inventory
from app.models.stock_movement import StockMovement
from app.api.v1.general_ledger import listing as ledger_listing
from app.api.v1.stock_reconciliation import listing as stock_listing
from app.services.goods_receipt_service import GoodsReceiptService


ADMIN = SimpleNamespace(
    id=1,
    roles=[SimpleNamespace(name="SYSTEM_ADMINISTRATOR")],
    default_location_id=None,
    location_id=None,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()
    engine.dispose()


def _account(db, code):
    item = ChartOfAccount(
        account_number=code, account_name=f"Account {code}",
        account_type="ASSET", normal_balance="DEBIT",
        is_active=True, is_posting=True,
    )
    db.add(item)
    db.flush()
    return item


def test_gl_range_search_and_full_totals_ignore_draft(db):
    low, middle, high = (_account(db, code) for code in ("1000", "2000", "3000"))
    supplier = Supplier(code="SUP-1", name="Supplier One", is_active=True)
    db.add(supplier)
    db.flush()
    for account, status, value in (
        (low, "POSTED", "10"), (middle, "POSTED", "20"),
        (high, "POSTED", "30"), (middle, "DRAFT", "999"),
    ):
        journal = JournalEntry(
            journal_number=f"JV-{account.account_number}-{status}",
            posting_date=date(2026, 9, 1), status=status,
            reference_type="MANUAL", reference_id=0,
            document_number=f"DOC-{account.account_number}",
        )
        journal.lines = [JournalLine(
            account_id=account.id, supplier_id=supplier.id,
            debit=Decimal(value), credit=Decimal("0"),
        )]
        db.add(journal)
    db.commit()

    result = ledger_listing(
        page=1, page_size=1, search="Supplier One",
        search_type="SUPPLIER", account_id=None,
        account_from_id=low.id, account_to_id=middle.id,
        date_from=None, date_to=None, reference_type=None,
        supplier_id=None, department_id=None, location_id=None,
        business_unit_id=None, db=db, user=ADMIN,
    )
    assert result["total_items"] == 2
    assert len(result["items"]) == 1
    assert result["summary"]["total_debit"] == Decimal("30")
    assert result["summary"]["total_credit"] == Decimal("0")


def test_stock_reconciliation_empty_contract(db):
    result = stock_listing(
        fiscal_year=2026, location_id=None, warehouse_id=None,
        status=None, search=None, page=1, page_size=50, db=db, user=ADMIN,
    )
    assert result["items"] == []
    assert result["summary"]["variance_qty"] == Decimal("0")


def test_receiving_before_2026_rejected_at_service_boundary():
    data = SimpleNamespace(received_at=datetime(2025, 12, 31, tzinfo=timezone.utc))
    with pytest.raises(HTTPException) as error:
        GoodsReceiptService.create(db=None, data=data, user=ADMIN)
    assert error.value.status_code == 422


def test_stock_reconciliation_uses_movement_cutoff_and_current_snapshot(db):
    product = Product(
        code="ITEM-1", name="Item", group_code="1", group_name="Food",
        subgroup_code="1", subgroup_name="Food", uom="PCS",
        usage_uom="PCS", is_active=True,
    )
    warehouse = Warehouse(code="WH-1", name="Warehouse", is_active=True)
    db.add_all([product, warehouse])
    db.flush()
    db.add(Inventory(product_id=product.id, warehouse_id=warehouse.id,
                     quantity=Decimal("16"), average_cost=Decimal("1")))
    db.add_all([
        StockMovement(product_id=product.id, warehouse_id=warehouse.id,
                      movement_type="IN", quantity=Decimal("10"), unit_cost=Decimal("1"),
                      created_at=datetime(2025, 12, 20, tzinfo=timezone.utc)),
        StockMovement(product_id=product.id, warehouse_id=warehouse.id,
                      movement_type="IN", quantity=Decimal("5"), unit_cost=Decimal("1"),
                      created_at=datetime(2026, 1, 10, tzinfo=timezone.utc)),
    ])
    db.commit()
    result = stock_listing(
        fiscal_year=2026, location_id=None, warehouse_id=None,
        status=None, search=None, page=1, page_size=50, db=db, user=ADMIN,
    )
    row = result["items"][0]
    assert row["closing_2025_qty"] == Decimal("10")
    assert row["opening_2026_qty"] == Decimal("11")
    assert row["variance_qty"] == Decimal("-1")
    assert row["status"] == "VARIANCE"
