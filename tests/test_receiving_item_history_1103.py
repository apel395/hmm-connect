"""Item-history search is read-only, paginated and restricted to visible RRs."""
from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.v1.goods_receipts import received_item_history
from app.models import Base
from app.models.goods_receipt import GoodsReceipt, GoodsReceiptItem
from app.models.product import Product


def test_item_history_finds_each_receiving_line_and_its_original_date():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            blender = Product(
                code="BL-001", name="BLANDER PHILIPS", group_code="4",
                group_name="Equipment", subgroup_code="4-1", subgroup_name="Tools",
                uom="PCS", usage_uom="PCS", item_type="BUY",
                catalog_type="HOTEL", inventory_treatment="STOCK",
            )
            db.add(blender)
            db.flush()
            for number, day, location, status, cost in (
                ("RR-A", 1, 10, "POSTED", 1200),
                ("RR-B", 3, 10, "DRAFT", 1500),
                ("RR-C", 2, 20, "POSTED", 1300),
            ):
                db.add(GoodsReceipt(
                    receipt_number=number, status=status, location_id=location,
                    received_at=datetime(2026, 11, day, 1, tzinfo=timezone.utc),
                    items=[GoodsReceiptItem(
                        product_id=blender.id, quantity=2, unit_cost=cost,
                        is_taxable=False, tax_rate=0,
                    )],
                ))
            db.commit()

            scoped_user = SimpleNamespace(roles=[], default_location_id=10)
            result = received_item_history(
                search="blander", page=1, page_size=50, db=db, user=scoped_user,
            )
            assert result["total_items"] == 2
            assert [row["receipt_number"] for row in result["items"]] == ["RR-B", "RR-A"]
            assert result["items"][0]["status"] == "DRAFT"
            assert result["items"][1]["received_at"].day == 1
            assert result["items"][1]["unit_cost"] == 1200

            first_page = received_item_history(
                search="BL-001", page=1, page_size=1, db=db, user=scoped_user,
            )
            assert first_page["total_pages"] == 2
            assert len(first_page["items"]) == 1
            assert received_item_history(
                search="no matching product", page=1, page_size=50,
                db=db, user=scoped_user,
            )["total_items"] == 0
    finally:
        engine.dispose()
