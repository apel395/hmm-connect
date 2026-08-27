from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_permission
from app.models.goods_receipt import GoodsReceipt
from app.models.supplier_invoice import SupplierInvoice

router = APIRouter(prefix="/supplier-invoice-sources", tags=["Supplier Invoices"])


def _access(user):
    if not has_permission(user, "supplier_invoice.view"):
        raise HTTPException(status_code=403, detail="Finance access required")


@router.get("/eligible-receipts")
def eligible_receipts(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    _access(user)

    used_receipt_ids = {
        receipt_id
        for (receipt_id,) in (
            db.query(SupplierInvoice.goods_receipt_id)
            .filter(
                SupplierInvoice.goods_receipt_id.isnot(None),
                SupplierInvoice.status.notin_(("REJECTED", "VOID")),
            )
            .distinct()
            .all()
        )
    }

    receipts = (
        db.query(GoodsReceipt)
        .filter(GoodsReceipt.status == "POSTED")
        .order_by(GoodsReceipt.received_at.desc(), GoodsReceipt.id.desc())
        .all()
    )

    return [
        {
            "id": receipt.id,
            "receipt_number": receipt.receipt_number,
            "purchase_order_id": receipt.purchase_order_id,
            "supplier_id": receipt.supplier_id or (receipt.purchase_order.supplier_id if receipt.purchase_order else None),
            "supplier_name": receipt.supplier.name if receipt.supplier else receipt.purchase_order.supplier.name if receipt.purchase_order and receipt.purchase_order.supplier else None,
            "business_unit_id": receipt.business_unit_id,
            "department_id": receipt.department_id,
            "location_id": receipt.location_id,
            "received_at": receipt.received_at,
        }
        for receipt in receipts
        if receipt.id not in used_receipt_ids
    ]
