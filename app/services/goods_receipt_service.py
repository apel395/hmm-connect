from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.goods_receipt import GoodsReceipt, GoodsReceiptItem
from app.models.inventory import Inventory
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.stock_movement import StockMovement
from app.models.warehouse import Warehouse
from app.schemas.goods_receipt import GoodsReceiptCreate
from app.services.activity_service import ActivityService


class GoodsReceiptService:
    @staticmethod
    def _number(db: Session) -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        count = (
            db.query(GoodsReceipt)
            .filter(GoodsReceipt.receipt_number.like(f"GR-{stamp}-%"))
            .count()
            + 1
        )
        return f"GR-{stamp}-{count:05d}"

    @classmethod
    def receive(cls, db: Session, *, data: GoodsReceiptCreate, user):
        purchase_order = db.get(PurchaseOrder, data.purchase_order_id)
        if not purchase_order:
            raise HTTPException(status_code=404, detail="Purchase order not found")
        if purchase_order.status not in {"APPROVED", "PARTIALLY_RECEIVED"}:
            raise HTTPException(
                status_code=400,
                detail="Only approved purchase orders can be received",
            )
        if not db.get(Warehouse, data.warehouse_id):
            raise HTTPException(status_code=404, detail="Warehouse not found")
        if not data.items:
            raise HTTPException(status_code=400, detail="Receipt must contain items")

        receipt = GoodsReceipt(
            receipt_number=cls._number(db),
            purchase_order_id=purchase_order.id,
            received_by_id=user.id,
            received_at=data.received_at or datetime.now(timezone.utc),
            source_type=data.source_type,
            external_reference=data.external_reference,
            receipt_type=data.receipt_type,
            destination_type=data.destination_type,
            warehouse_id=data.warehouse_id,
            notes=data.notes,
        )
        db.add(receipt)
        db.flush()

        for incoming in data.items:
            item = db.get(PurchaseOrderItem, incoming.purchase_order_item_id)
            if not item or item.purchase_order_id != purchase_order.id:
                raise HTTPException(
                    status_code=400,
                    detail="Receipt item does not belong to the purchase order",
                )
            tolerance = Decimal(purchase_order.receipt_tolerance_percent or 0)
            allowed_total = Decimal(item.quantity) * (
                Decimal("1") + tolerance / Decimal("100")
            )
            remaining = allowed_total - Decimal(item.received_quantity or 0)
            if incoming.quantity > remaining:
                raise HTTPException(
                    status_code=400,
                    detail=f"Quantity exceeds remaining amount for PO item {item.id}",
                )

            unit_cost = Decimal(item.unit_price)

            receipt.items.append(
                GoodsReceiptItem(
                    purchase_order_item_id=item.id,
                    product_id=item.product_id,
                    quantity=incoming.quantity,
                    unit_cost=unit_cost,
                )
            )
            item.received_quantity = Decimal(item.received_quantity or 0) + incoming.quantity

            if data.destination_type == "INVENTORY":
                inventory = (
                    db.query(Inventory)
                    .filter(
                        Inventory.product_id == item.product_id,
                        Inventory.warehouse_id == data.warehouse_id,
                    )
                    .first()
                )
                if not inventory:
                    inventory = Inventory(
                        product_id=item.product_id,
                        warehouse_id=data.warehouse_id,
                        quantity=Decimal("0"),
                        average_cost=Decimal("0"),
                    )
                    db.add(inventory)
                    db.flush()

                old_quantity = Decimal(inventory.quantity or 0)
                old_value = old_quantity * Decimal(inventory.average_cost or 0)
                new_quantity = old_quantity + incoming.quantity
                inventory.quantity = new_quantity
                inventory.average_cost = (
                    old_value + incoming.quantity * unit_cost
                ) / new_quantity

            db.add(
                StockMovement(
                    product_id=item.product_id,
                    warehouse_id=data.warehouse_id,
                    goods_receipt_id=receipt.id,
                    movement_type=(
                        "IN"
                        if data.destination_type == "INVENTORY"
                        else "DIRECT_CONSUMPTION"
                    ),
                    quantity=incoming.quantity,
                    unit_cost=unit_cost,
                    reference_type="GOODS_RECEIPT",
                    reference_id=receipt.id,
                )
            )

        fully_received = all(
            Decimal(item.received_quantity or 0) >= Decimal(item.quantity)
            for item in purchase_order.items
        )
        purchase_order.status = "RECEIVED" if fully_received else "PARTIALLY_RECEIVED"
        ActivityService.log(
            db=db,
            user=user,
            action="RECEIVE",
            entity_type="GOODS_RECEIPT",
            entity_id=receipt.id,
            summary=f"Received goods as {receipt.receipt_number}",
            document_type="GR",
            document_number=receipt.receipt_number,
            document_status="POSTED",
            reference_document=purchase_order.po_number,
            details={
                "purchase_order_id": purchase_order.id,
                "warehouse_id": data.warehouse_id,
                "destination_type": data.destination_type,
                "item_count": len(data.items),
            },
        )
        db.commit()
        db.refresh(receipt)
        return receipt
