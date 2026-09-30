from datetime import datetime, timezone, date
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.goods_receipt import GoodsReceipt, GoodsReceiptItem
from app.models.product import Product
from app.models.supplier import Supplier
from app.services.purchasing_insights_service import PurchasingInsightsService


def test_posted_receipts_drive_rankings_and_price_history():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    user = SimpleNamespace(
        roles=[SimpleNamespace(name="SYSTEM_ADMINISTRATOR")],
        default_location_id=None, location_id=None,
    )
    try:
        supplier = Supplier(code="TOP-SUP", name="Supplier", is_active=True)
        product = Product(code="TOP-ITEM", name="Product", group_code="1",
                          group_name="Food", subgroup_code="1", subgroup_name="Food",
                          uom="PCS", usage_uom="PCS", is_active=True)
        db.add_all([supplier, product])
        db.flush()
        for status, day, qty, unit_cost in (
            ("POSTED", 5, "2", "100"), ("POSTED", 20, "3", "120"),
            ("DRAFT", 21, "99", "999"),
        ):
            receipt = GoodsReceipt(
                receipt_number=f"TOP-{status}-{day}",
                status=status, supplier_id=supplier.id,
                received_at=datetime(2026, 9, day, tzinfo=timezone.utc),
            )
            receipt.items.append(GoodsReceiptItem(
                product_id=product.id, quantity=Decimal(qty),
                unit_cost=Decimal(unit_cost),
            ))
            db.add(receipt)
        db.commit()
        service = PurchasingInsightsService(db, user)
        rankings = service.rankings(year=2026, month=9)
        assert rankings["top_items_by_quantity"][0]["quantity"] == Decimal("5")
        assert rankings["top_items_by_cost"][0]["received_value"] == Decimal("560")
        assert rankings["top_suppliers_by_receipts"][0]["receipt_count"] == 2
        history = service.price_history(
            product_id=product.id, date_from=date(2026, 9, 1),
            date_to=date(2026, 9, 30),
        )
        assert history["total_items"] == 2
        assert [row["unit_cost"] for row in history["items"]] == [
            Decimal("120"), Decimal("100"),
        ]
    finally:
        db.close()
        engine.dispose()
