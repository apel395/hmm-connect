from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_any_role
from app.models.goods_receipt import GoodsReceipt, GoodsReceiptItem
from app.models.supplier_invoice import SupplierInvoice, SupplierInvoiceLine

router = APIRouter(prefix="/supplier-invoice-sources", tags=["Supplier Invoices"])
ZERO = Decimal("0")


def _access(user):
    if not has_any_role(user, "FINANCE"):
        raise HTTPException(status_code=403, detail="Finance access required")


@router.get("/eligible-receipts")
def eligible_receipts(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    _access(user)

    invoiced_rows = (
        db.query(
            SupplierInvoiceLine.goods_receipt_item_id,
            func.coalesce(func.sum(SupplierInvoiceLine.quantity), 0),
        )
        .join(SupplierInvoice, SupplierInvoice.id == SupplierInvoiceLine.supplier_invoice_id)
        .filter(
            SupplierInvoiceLine.goods_receipt_item_id.isnot(None),
            SupplierInvoice.status.notin_(("REJECTED", "VOID")),
        )
        .group_by(SupplierInvoiceLine.goods_receipt_item_id)
        .all()
    )
    invoiced_by_item = {
        item_id: Decimal(quantity or 0)
        for item_id, quantity in invoiced_rows
    }

    receipts = (
        db.query(GoodsReceipt)
        .filter(GoodsReceipt.status == "POSTED")
        .order_by(GoodsReceipt.received_at.desc(), GoodsReceipt.id.desc())
        .all()
    )

    result = []
    for receipt in receipts:
        remaining_lines = []
        for item in receipt.items:
            received = Decimal(item.quantity or 0)
            already_invoiced = invoiced_by_item.get(item.id, ZERO)
            remaining = max(ZERO, received - already_invoiced)
            if remaining <= 0:
                continue
            remaining_lines.append({
                "id": item.id,
                "goods_receipt_item_id": item.id,
                "purchase_order_item_id": item.purchase_order_item_id,
                "product_id": item.product_id,
                "product_code": item.product.code if item.product else None,
                "product_name": item.product.name if item.product else None,
                "description": item.product.name if item.product else f"Item #{item.product_id}",
                "uom": (
                    item.purchase_order_item.uom
                    if item.purchase_order_item and item.purchase_order_item.uom
                    else item.product.uom if item.product else None
                ),
                "received_quantity": received,
                "already_invoiced_quantity": already_invoiced,
                "remaining_quantity": remaining,
                "unit_cost": item.unit_cost,
            })

        if not remaining_lines:
            continue

        result.append({
            "id": receipt.id,
            "receipt_number": receipt.receipt_number,
            "purchase_order_id": receipt.purchase_order_id,
            "supplier_id": receipt.supplier_id or (receipt.purchase_order.supplier_id if receipt.purchase_order else None),
            "supplier_name": receipt.supplier.name if receipt.supplier else receipt.purchase_order.supplier.name if receipt.purchase_order and receipt.purchase_order.supplier else None,
            "business_unit_id": receipt.business_unit_id,
            "department_id": receipt.department_id,
            "location_id": receipt.location_id,
            "received_at": receipt.received_at,
            "items": remaining_lines,
        })

    return result
