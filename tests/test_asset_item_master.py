from datetime import date
from decimal import Decimal
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, insert, select
from sqlalchemy.orm import Session
from app.models import Base
from app.models.chart_of_account import ChartOfAccount
from app.models.item_group import ItemGroup
from app.models.item_subgroup import ItemSubgroup
from app.models.product import Product
from app.models.supplier_invoice import SupplierInvoice, SupplierInvoiceLine
from app.services import asset_item_master as intake

USER = SimpleNamespace(id=45)

@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(intake, "record_audit", lambda *a, **kw: None)
    with Session(engine) as db:
        db.add(ChartOfAccount(id=215, account_number="100-600-104", account_name="FF&E", account_type="ASSET", normal_balance="DEBIT", is_active=True, is_posting=True))
        group = ItemGroup(code="4", name="ASSET", item_type="ITEM", is_active=True)
        group.subgroups = [ItemSubgroup(code="4-4", name="KOMPUTER", is_active=True), ItemSubgroup(code="4-2", name="FURNITURE", is_active=True)]
        db.add(group); db.commit()
        yield db
    engine.dispose()


def item(db, **kw):
    return intake.ensure_asset_item(db, name="Intel i5 computer", account_id=215, user=USER, **kw)


def test_manual_asset_creates_and_reuses_buy_item_with_no_stock(db):
    first = item(db)
    second = item(db)
    assert first.id == second.id
    assert first.code == "4-400001" and first.subgroup_name == "KOMPUTER"
    assert first.inventory_treatment == "FIXED_ASSET" and first.item_type == "BUY"
    assert first.asset_account_id == 215
    assert first.inventory_account_id is None and first.cogs_account_id is None
    assert first.inventory == []
    assert db.query(Product).count() == 1


def test_conflicting_existing_classification_is_not_rewritten(db):
    first = item(db)
    first.inventory_treatment = "STOCK"; db.flush()
    with pytest.raises(HTTPException) as error: item(db)
    assert error.value.status_code == 409
    assert first.inventory_treatment == "STOCK"


def test_explicit_sell_or_inactive_item_is_rejected(db):
    first = item(db); first.item_type = "SELL"; db.flush()
    with pytest.raises(HTTPException): item(db, product_id=first.id)


def test_posted_invoice_link_preserves_tax_and_totals_and_is_repeatable(db):
    db.execute(insert(SupplierInvoice).values(id=611, internal_invoice_number="INV-611", supplier_invoice_number="HIST-13", supplier_id=1, invoice_date=date(2026,1,8), subtotal=5500000, tax_amount=605000, total_amount=6105000, balance_amount=6105000, status="POSTED"))
    db.execute(insert(SupplierInvoiceLine).values(id=900, supplier_invoice_id=611, description="Intel i5 computer", quantity=1, uom="SET", unit_price=5500000, line_amount=5500000, is_taxable=True, tax_rate=11, tax_amount=605000, account_id=215))
    db.commit()
    before = dict(db.execute(select(SupplierInvoice.__table__)).mappings().one())
    line = db.get(SupplierInvoiceLine, 900)
    asset = SimpleNamespace(id=2, asset_number="FA-TEST", product_id=None, source_invoice_line_id=900, goods_receipt_id=None, asset_name="Computer", asset_account_id=215)
    first = intake.link_asset_item(db, asset, user=USER)
    db.flush()
    assert line.product_id == first.id and asset.product_id == first.id
    assert line.tax_amount == Decimal("605000") and line.line_amount == Decimal("5500000")
    assert dict(db.execute(select(SupplierInvoice.__table__)).mappings().one()) == before
    assert intake.link_asset_item(db, asset, user=USER).id == first.id
    assert db.query(Product).count() == 1
    db.rollback()
    assert db.query(Product).count() == 0 and db.get(SupplierInvoiceLine, 900).product_id is None
