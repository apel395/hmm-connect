from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.account_receipt import AccountReceipt
from app.models.chart_of_account import ChartOfAccount
from app.models.goods_receipt import GoodsReceipt, GoodsReceiptItem
from app.models.inventory import Inventory
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.stock_movement import StockMovement
from app.models.warehouse import Warehouse
from app.services.audit import record_audit
from app.schemas.goods_receipt import GoodsReceiptCreate, GoodsReceiptResponse

router = APIRouter(prefix="/goods-receipts", tags=["Goods Receipts"])


def generate_receipt_number(db: Session) -> str:
    count = db.query(GoodsReceipt).count() + 1
    return f"GR-{count:06d}"


@router.get(
    "/purchase-orders/{purchase_order_id}",
    response_model=list[GoodsReceiptResponse],
)
def get_purchase_order_receipts(
    purchase_order_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return (
        db.query(GoodsReceipt)
        .options(joinedload(GoodsReceipt.items))
        .filter(GoodsReceipt.purchase_order_id == purchase_order_id)
        .order_by(GoodsReceipt.id.desc())
        .all()
    )


@router.post(
    "/purchase-orders/{purchase_order_id}/receive",
    response_model=GoodsReceiptResponse,
)
def receive_goods(
    purchase_order_id: int,
    data: GoodsReceiptCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    purchase_order = (
        db.query(PurchaseOrder)
        .options(joinedload(PurchaseOrder.items))
        .filter(PurchaseOrder.id == purchase_order_id)
        .first()
    )

    if not purchase_order:
        raise HTTPException(status_code=404, detail="Purchase order not found")

    if not data.items:
        raise HTTPException(status_code=400, detail="Goods receipt must have items")

    if purchase_order.expiry_date and purchase_order.expiry_date < date.today():
        raise HTTPException(status_code=400, detail="Purchase order has expired")

    destination_type = data.destination_type.upper()
    if destination_type not in {"INVENTORY", "DIRECT_CONSUMPTION"}:
        raise HTTPException(status_code=400, detail="Invalid receipt destination")

    warehouse = None
    if destination_type == "INVENTORY":
        if data.warehouse_id is None:
            raise HTTPException(status_code=400, detail="Warehouse is required for inventory receipt")
        warehouse = (
            db.query(Warehouse)
            .filter(Warehouse.id == data.warehouse_id, Warehouse.is_active.is_(True))
            .first()
        )
        if not warehouse:
            raise HTTPException(status_code=404, detail="Warehouse not found")

    direct_account = None
    if destination_type == "DIRECT_CONSUMPTION":
        direct_account = (
            db.query(ChartOfAccount)
            .filter(
                ChartOfAccount.account_number == "5200",
                ChartOfAccount.is_active.is_(True),
            )
            .first()
        )
        if not direct_account:
            raise HTTPException(status_code=500, detail="Direct consumption account is not configured")

    receipt = GoodsReceipt(
        receipt_number=generate_receipt_number(db),
        purchase_order_id=purchase_order.id,
        received_by_id=current_user.id,
        destination_type=destination_type,
        warehouse_id=warehouse.id if warehouse else None,
        notes=data.notes,
    )

    db.add(receipt)
    db.flush()

    tolerance = purchase_order.receipt_tolerance_percent / Decimal("100")

    for receive_item in data.items:
        item = next(
            (
                order_item
                for order_item in purchase_order.items
                if order_item.id == receive_item.purchase_order_item_id
            ),
            None,
        )

        if not item:
            raise HTTPException(status_code=404, detail="Purchase order item not found")

        if receive_item.quantity <= 0:
            raise HTTPException(status_code=400, detail="Receive quantity must be greater than zero")

        allowed_quantity = item.quantity * (Decimal("1") + tolerance)
        new_received_quantity = item.received_quantity + receive_item.quantity

        if new_received_quantity > allowed_quantity:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Receipt exceeds PO tolerance. Maximum allowed quantity is "
                    f"{allowed_quantity}"
                ),
            )

        receipt.items.append(
            GoodsReceiptItem(
                purchase_order_item_id=item.id,
                product_id=item.product_id,
                quantity=receive_item.quantity,
                unit_cost=item.unit_price,
            )
        )

        if destination_type == "INVENTORY":
            inventory = (
                db.query(Inventory)
                .filter(
                    Inventory.product_id == item.product_id,
                    Inventory.warehouse_id == warehouse.id,
                )
                .first()
            )

            if not inventory:
                inventory = Inventory(
                    product_id=item.product_id,
                    warehouse_id=warehouse.id,
                    quantity=Decimal("0"),
                    average_cost=Decimal("0"),
                )
                db.add(inventory)
                db.flush()

            old_quantity = inventory.quantity
            new_quantity = old_quantity + receive_item.quantity

            if new_quantity > 0:
                inventory.average_cost = (
                    (old_quantity * inventory.average_cost)
                    + (receive_item.quantity * item.unit_price)
                ) / new_quantity

            inventory.quantity = new_quantity

            movement = StockMovement(
                product_id=item.product_id,
                warehouse_id=warehouse.id,
                goods_receipt_id=receipt.id,
                movement_type="PURCHASE_RECEIPT",
                quantity=receive_item.quantity,
                unit_cost=item.unit_price,
                reference_type="GOODS_RECEIPT",
                reference_id=receipt.id,
                notes=f"Stock received from {receipt.receipt_number}",
            )
            db.add(movement)
            db.flush()

            record_audit(
                db=db,
                user=current_user,
                action="STOCK_IN",
                entity_type="STOCK_MOVEMENT",
                entity_id=movement.id,
                summary=f"Added {receive_item.quantity} units to inventory from {receipt.receipt_number}",
                details={
                    "goods_receipt_id": receipt.id,
                    "purchase_order_id": purchase_order.id,
                    "purchase_order_item_id": item.id,
                    "product_id": item.product_id,
                    "warehouse_id": warehouse.id,
                    "quantity": str(receive_item.quantity),
                    "unit_cost": str(item.unit_price),
                },
            )
        else:
            account_receipt = AccountReceipt(
                goods_receipt_id=receipt.id,
                product_id=item.product_id,
                account_id=direct_account.id,
                quantity=receive_item.quantity,
                unit_cost=item.unit_price,
                total_amount=receive_item.quantity * item.unit_price,
            )
            db.add(account_receipt)
            db.flush()

            record_audit(
                db=db,
                user=current_user,
                action="DIRECT_CONSUMPTION",
                entity_type="ACCOUNT_RECEIPT",
                entity_id=account_receipt.id,
                summary=f"Recorded direct consumption from {receipt.receipt_number}",
                details={
                    "goods_receipt_id": receipt.id,
                    "purchase_order_id": purchase_order.id,
                    "product_id": item.product_id,
                    "account_id": direct_account.id,
                    "quantity": str(receive_item.quantity),
                    "unit_cost": str(item.unit_price),
                },
            )

        item.received_quantity += receive_item.quantity

    all_received = all(
        item.received_quantity >= item.quantity
        for item in purchase_order.items
    )
    any_received = any(item.received_quantity > 0 for item in purchase_order.items)

    if all_received:
        purchase_order.status = "RECEIVED"
    elif any_received:
        purchase_order.status = "PARTIALLY_RECEIVED"

    record_audit(
        db=db,
        user=current_user,
        action="CREATE",
        entity_type="GOODS_RECEIPT",
        entity_id=receipt.id,
        summary=f"Created goods receipt {receipt.receipt_number}",
        details={
            "receipt_number": receipt.receipt_number,
            "purchase_order_id": purchase_order.id,
            "destination_type": destination_type,
            "warehouse_id": warehouse.id if warehouse else None,
            "status": purchase_order.status,
        },
    )

    db.commit()
    db.refresh(receipt)
    return receipt
