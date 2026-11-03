from datetime import datetime, timezone, date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base
from app.models.chart_of_account import ChartOfAccount
from app.models.fixed_asset import FixedAsset, FixedAssetMovement
from app.models.goods_receipt import GoodsReceipt, GoodsReceiptItem
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.product import Product
from app.models.general_ledger import GeneralLedger
from app.services.receipt_asset_registration import (
    register_posted_receipt_assets, sync_pending_receipt_assets,
)

USER = SimpleNamespace(id=1, roles=[])


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(ChartOfAccount(
            id=1, account_number="100-600-104", account_name="Equipment",
            account_type="ASSET", normal_balance="DEBIT", is_active=True, is_posting=True,
        ))
        session.commit()
        yield session
    engine.dispose()


def product(db, code="4-200101"):
    p = Product(
        code=code, name="Equipment", group_code="4", group_name="ASSET",
        subgroup_code="4-2", subgroup_name="FURNITURE", uom="PCS", usage_uom="PCS",
        item_type="BUY", catalog_type="HOTEL", inventory_treatment="FIXED_ASSET",
        asset_account_id=1,
    )
    db.add(p)
    db.commit()
    return p


def receipt(db, p, number, quantity=2, unit_cost=1500, status="POSTED"):
    rec = GoodsReceipt(
        receipt_number=number, status=status, source_type="LIVE",
        received_at=datetime(2026, 11, 2, 18, 30, tzinfo=timezone.utc),
        business_unit_id=1, location_id=5, department_id=6, supplier_id=10,
        destination_type="DIRECT_USE",
        items=[GoodsReceiptItem(
            product_id=p.id, quantity=quantity, unit_cost=unit_cost,
            destination_type="DIRECT_USE", is_taxable=False, tax_rate=0,
        )],
    )
    db.add(rec)
    db.commit()
    return rec


def source_journal(db, rec, account_id=1, debit=3000):
    entry = JournalEntry(
        journal_number="JV-" + rec.receipt_number, posting_date=date(2026, 11, 3),
        status="DRAFT", reference_type="GOODS_RECEIPT", reference_id=rec.id,
    )
    entry.lines.append(JournalLine(account_id=account_id, debit=debit, credit=0))
    db.add(entry)
    db.commit()
    return entry


def test_posted_receipt_reuses_pending_asset_and_uses_actual_source(db):
    p = product(db)
    original = db.query(FixedAsset).one()
    assert original.status == "PENDING_REGISTRATION"
    rec = receipt(db, p, "GR-ASSET-1")
    assert register_posted_receipt_assets(db, receipt=rec, user=USER) == 1
    db.commit()
    asset = db.query(FixedAsset).one()
    assert asset.id == original.id
    assert asset.goods_receipt_id == rec.id
    assert asset.source_type == "GOODS_RECEIPT"
    assert asset.status == "PENDING_SETUP"
    assert asset.acquisition_date == date(2026, 11, 3)  # Jakarta business date
    assert asset.acquisition_cost == Decimal("3000")
    assert asset.net_book_value == Decimal("3000")
    assert asset.quantity == Decimal("2")
    assert asset.external_reference == rec.receipt_number
    assert db.query(FixedAssetMovement).count() == 1
    assert db.query(JournalEntry).count() == db.query(GeneralLedger).count() == 0


def test_duplicate_source_registration_is_idempotent(db):
    p = product(db)
    rec = receipt(db, p, "GR-ASSET-2")
    assert register_posted_receipt_assets(db, receipt=rec, user=USER) == 1
    db.commit()
    assert register_posted_receipt_assets(db, receipt=rec, user=USER) == 0
    db.commit()
    assert db.query(FixedAsset).count() == db.query(FixedAssetMovement).count() == 1


def test_separate_receipts_keep_separate_costs_and_quantities(db):
    p = product(db)
    first = receipt(db, p, "GR-ASSET-3", quantity=1, unit_cost=2000)
    assert register_posted_receipt_assets(db, receipt=first, user=USER) == 1
    db.commit()
    second = receipt(db, p, "GR-ASSET-4", quantity=3, unit_cost=2500)
    assert register_posted_receipt_assets(db, receipt=second, user=USER) == 1
    db.commit()
    assets = db.query(FixedAsset).order_by(FixedAsset.id).all()
    assert len(assets) == 2
    assert {a.goods_receipt_id: (a.acquisition_cost, a.quantity) for a in assets} == {
        first.id: (Decimal("2000"), Decimal("1")),
        second.id: (Decimal("7500"), Decimal("3")),
    }


def test_receipt_draft_does_not_register_asset(db):
    p = product(db)
    rec = receipt(db, p, "GR-ASSET-5", status="DRAFT")
    assert register_posted_receipt_assets(db, receipt=rec, user=USER) == 0
    db.commit()
    asset = db.query(FixedAsset).one()
    assert asset.status == "PENDING_REGISTRATION"
    assert asset.goods_receipt_id is None


def test_existing_pending_asset_relinks_only_with_unique_posted_receipt_and_journal(db):
    p = product(db)
    rec = receipt(db, p, "GR-ASSET-6")
    assert sync_pending_receipt_assets(db, user=USER) == 0  # no accounting evidence
    source_journal(db, rec)
    assert sync_pending_receipt_assets(db, user=USER) == 1
    db.commit()
    assert db.query(FixedAsset).one().goods_receipt_id == rec.id
    assert sync_pending_receipt_assets(db, user=USER) == 0
    assert db.query(FixedAsset).count() == 1


def test_backfill_does_not_guess_between_multiple_receipts(db):
    p = product(db)
    a = receipt(db, p, "GR-ASSET-7")
    b = receipt(db, p, "GR-ASSET-8")
    source_journal(db, a)
    source_journal(db, b)
    assert sync_pending_receipt_assets(db, user=USER) == 0
    asset = db.query(FixedAsset).one()
    assert asset.goods_receipt_id is None
    assert asset.acquisition_date is None
    assert asset.acquisition_cost is None


def test_backfill_rejects_mismatched_receiving_accounting(db):
    p = product(db)
    rec = receipt(db, p, "GR-ASSET-9")
    source_journal(db, rec, debit=1500)  # wrong source value
    assert sync_pending_receipt_assets(db, user=USER) == 0
    assert db.query(FixedAsset).one().goods_receipt_id is None
