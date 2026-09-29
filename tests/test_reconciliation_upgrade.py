from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.chart_of_account import ChartOfAccount
from app.models.inventory import Inventory
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.payment import Payment
from app.models.product import Product
from app.models.stock_movement import StockMovement
from app.models.warehouse import Warehouse
from app.services.financial_reconciliation_service import FinancialReconciliationService


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()
    engine.dispose()


def _account(db, number, name):
    row = ChartOfAccount(
        account_number=number, account_name=name,
        account_type="ASSET", normal_balance="DEBIT",
        is_active=True, is_posting=True,
    )
    db.add(row)
    db.flush()
    return row


def _journal(db, account, day, debit, credit):
    row = JournalEntry(
        journal_number=f"MAN-{account.id}-{day}", posting_date=date(2026, 1, day),
        status="POSTED", reference_type="MANUAL", reference_id=0,
        document_number=f"DOC-{account.id}-{day}",
    )
    row.lines = [JournalLine(
        account_id=account.id, debit=Decimal(debit), credit=Decimal(credit),
    )]
    db.add(row)


def test_inventory_reconciliation_uses_snapshot_and_signed_movements(db):
    food = _account(db, "100-300-100", "Inv Makanan")
    material = _account(db, "100-300-700", "Inv Material")
    warehouse = Warehouse(code="WH-1", name="Warehouse", is_active=True)
    products = [
        Product(code=code, name=code, group_code="1", group_name="Food",
                subgroup_code="1", subgroup_name="Food", uom="PCS",
                usage_uom="PCS", inventory_account_id=account.id, is_active=True)
        for code, account in (("FOOD", food), ("MAT", material))
    ]
    db.add_all([warehouse, *products])
    db.flush()
    db.add_all([
        Inventory(product_id=products[0].id, warehouse_id=warehouse.id,
                  quantity=Decimal("8"), average_cost=Decimal("10")),
        Inventory(product_id=products[1].id, warehouse_id=warehouse.id,
                  quantity=Decimal("1"), average_cost=Decimal("20")),
        StockMovement(product_id=products[0].id, warehouse_id=warehouse.id,
                      inventory_account_id=food.id, movement_type="IN",
                      quantity=Decimal("10"), unit_cost=Decimal("10"),
                      created_at=datetime(2026, 1, 2, tzinfo=timezone.utc)),
        StockMovement(product_id=products[0].id, warehouse_id=warehouse.id,
                      inventory_account_id=food.id, movement_type="OUT",
                      quantity=Decimal("2"), unit_cost=Decimal("10"),
                      created_at=datetime(2026, 1, 3, tzinfo=timezone.utc)),
    ])
    _journal(db, food, 2, "100", "0")
    _journal(db, food, 3, "0", "20")
    _journal(db, material, 2, "20", "0")
    db.commit()

    service = FinancialReconciliationService(db)
    current = service.inventory()
    assert current["source_balance"] == Decimal("100.00")
    assert current["gl_balance"] == Decimal("100")
    assert current["status"] == "RECONCILED"
    assert {row["account_code"] for row in current["detail"]} == {
        "100-300-100", "100-300-700",
    }
    food_detail = next(row for row in current["detail"]
                       if row["account_code"] == "100-300-100")
    assert food_detail["movement_value"] == Decimal("80")
    earlier = service.inventory(as_of=date(2026, 1, 2))
    assert earlier["source_balance"] == Decimal("120.00")
    assert earlier["gl_balance"] == Decimal("120")
    assert earlier["status"] == "RECONCILED"


def test_unallocated_posted_payment_is_visible(db):
    db.add(Payment(
        payment_number="PAY-202609-0004", payment_date=date(2026, 9, 26),
        amount=Decimal("7316281"), payment_method="BANK",
        status="POSTED", created_by_id=1,
    ))
    db.commit()
    rows = FinancialReconciliationService(db)._unallocated_payments(None, None)
    assert rows[0]["document_number"] == "PAY-202609-0004"
    assert rows[0]["amount"] == Decimal("7316281")


def test_inventory_chart_account_with_only_gl_opening_is_not_hidden(db):
    opening_account = _account(db, "100-300-999", "Persediaan Lainnya")
    _journal(db, opening_account, 1, "50", "0")
    db.commit()
    row = FinancialReconciliationService(db).inventory()
    assert row["status"] == "OUT_OF_BALANCE"
    assert row["source_balance"] == Decimal("0")
    assert row["gl_balance"] == Decimal("50")
    assert row["detail"][0]["account_code"] == "100-300-999"
