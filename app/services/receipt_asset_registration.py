"""Register the acquisition source of fixed assets from posted Goods Receipts."""
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.fixed_asset import FixedAsset, FixedAssetMovement
from app.models.goods_receipt import GoodsReceipt, GoodsReceiptItem
from app.models.journal_entry import JournalEntry
from app.models.product import Product
from app.services.audit import record_audit
from app.services.receiving_destination import line_destination

MONEY = Decimal("0.01")


def _receipt_asset_lines(db: Session, receipt: GoodsReceipt):
    grouped = defaultdict(list)
    for line in receipt.items:
        product = line.product or db.get(Product, line.product_id)
        if (
            product is not None
            and product.item_type == "BUY"
            and product.inventory_treatment == "FIXED_ASSET"
            and product.asset_account_id is not None
            and line_destination(receipt, line) == "DIRECT_USE"
            and Decimal(line.quantity or 0) > 0
            and Decimal(line.unit_cost or 0) > 0
        ):
            grouped[product.id].append((product, line))
    return grouped


def register_posted_receipt_assets(
    db: Session, *, receipt: GoodsReceipt, user, pending_only: bool = False,
) -> int:
    """Link actual accepted receipt quantities/costs without creating accounting journals.

    A receipt can contain multiple asset products or multiple lines for one product.
    One register record is linked to each product/receipt pair. A second receipt for
    the same item gets its own register entry rather than overwriting prior cost.
    """
    if receipt.status != "POSTED" or receipt.source_type == "HISTORICAL_IMPORT":
        return 0

    registered = 0
    for product_id, entries in sorted(_receipt_asset_lines(db, receipt).items()):
        existing = (
            db.query(FixedAsset)
            .filter(FixedAsset.goods_receipt_id == receipt.id, FixedAsset.product_id == product_id)
            .with_for_update()
            .first()
        )
        if existing:
            continue

        product = entries[0][0]
        amount = sum(
            (Decimal(line.quantity) * Decimal(line.unit_cost)).quantize(
                MONEY, rounding=ROUND_HALF_UP
            ) for _, line in entries
        )
        quantity = sum(Decimal(line.quantity) for _, line in entries)
        pending = (
            db.query(FixedAsset)
            .filter(
                FixedAsset.product_id == product_id,
                FixedAsset.status == "PENDING_REGISTRATION",
                FixedAsset.source_type == "ITEM_MASTER",
            )
            .with_for_update()
            .first()
        )
        if pending_only and pending is None:
            continue
        if pending and pending.asset_account_id != product.asset_account_id:
            continue

        asset = pending or FixedAsset(
            asset_number=f"FA-GR-{receipt.id:08d}-{product_id:08d}",
            product_id=product_id,
            asset_name=product.name,
            asset_account_id=product.asset_account_id,
        )
        asset.goods_receipt_id = receipt.id
        asset.purchase_order_id = receipt.purchase_order_id
        asset.supplier_id = receipt.supplier_id
        asset.business_unit_id = receipt.business_unit_id
        asset.location_id = receipt.location_id
        asset.department_id = receipt.department_id
        asset.acquisition_date = (
            receipt.received_at.astimezone(ZoneInfo("Asia/Jakarta")).date()
            if receipt.received_at.tzinfo else receipt.received_at.date()
        )
        asset.acquisition_cost = amount
        asset.quantity = quantity
        asset.net_book_value = amount
        asset.residual_value = Decimal("0")
        asset.accumulated_depreciation = Decimal("0")
        asset.source_type = "GOODS_RECEIPT"
        asset.external_reference = receipt.receipt_number
        asset.created_by_id = user.id
        asset.status = "DRAFT" if asset.asset_category_id else "PENDING_SETUP"
        db.add(asset)
        db.flush()
        db.add(FixedAssetMovement(
            fixed_asset_id=asset.id, movement_type="ACQUISITION",
            to_business_unit_id=receipt.business_unit_id,
            to_location_id=receipt.location_id,
            to_department_id=receipt.department_id,
            movement_date=asset.acquisition_date,
            reference_number=receipt.receipt_number,
            created_by_id=user.id,
        ))
        record_audit(
            db, user, "FIXED_ASSET_REGISTERED", "FIXED_ASSET",
            f"Linked fixed asset {asset.asset_number} to posted receiving {receipt.receipt_number}",
            entity_id=asset.id, reference_document=receipt.receipt_number,
            after_data={
                "product_id": product_id,
                "goods_receipt_id": receipt.id,
                "acquisition_date": asset.acquisition_date.isoformat(),
                "acquisition_cost": str(amount),
                "quantity": str(quantity),
            },
        )
        registered += 1
    return registered


def sync_pending_receipt_assets(db: Session, *, user) -> int:
    """Recover only unambiguous Item Master placeholders with accounting evidence.

    Never guess which historical RR applies when a product has multiple posted RRs.
    Never replace manually registered or already capitalized assets.
    """
    pending = db.query(FixedAsset).filter(
        FixedAsset.status == "PENDING_REGISTRATION",
        FixedAsset.source_type == "ITEM_MASTER",
        FixedAsset.product_id.is_not(None),
    ).all()
    registered = 0
    for asset in pending:
        candidates = (
            db.query(GoodsReceipt)
            .join(GoodsReceiptItem, GoodsReceiptItem.goods_receipt_id == GoodsReceipt.id)
            .filter(
                GoodsReceiptItem.product_id == asset.product_id,
                GoodsReceipt.status == "POSTED",
                GoodsReceipt.source_type.in_(("LIVE", "HISTORICAL_ENTRY")),
            )
            .distinct()
            .limit(2)
            .all()
        )
        if len(candidates) != 1:
            continue
        receipt = candidates[0]
        entries = _receipt_asset_lines(db, receipt)
        if asset.product_id not in entries:
            continue
        journal = (
            db.query(JournalEntry)
            .filter(
                JournalEntry.reference_type == "GOODS_RECEIPT",
                JournalEntry.reference_id == receipt.id,
                JournalEntry.status != "VOID",
            )
            .order_by(JournalEntry.id.desc())
            .first()
        )
        if journal is None:
            continue
        amount_for_account = sum(
            (
                (Decimal(line.quantity) * Decimal(line.unit_cost)).quantize(
                    MONEY, rounding=ROUND_HALF_UP
                )
                for groups in entries.values()
                for product, line in groups
                if product.asset_account_id == asset.asset_account_id
            ),
            Decimal("0"),
        )
        journal_debit = sum(
            (
                Decimal(line.debit or 0)
                for line in journal.lines
                if line.account_id == asset.asset_account_id
            ),
            Decimal("0"),
        )
        if journal_debit != amount_for_account:
            continue
        registered += register_posted_receipt_assets(
            db, receipt=receipt, user=user, pending_only=True,
        )
    return registered
