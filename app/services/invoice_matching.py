from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.account_payable import AccountPayable
from app.models.goods_receipt import GoodsReceipt
from app.models.purchase_order import PurchaseOrder


class InvoiceMatchingService:

    @staticmethod
    def verify(
        db: Session,
        payable: AccountPayable,
    ):

        if payable.purchase_order_id is None:

            payable.match_status = "NO_PO"

            payable.matched = False

            payable.match_note = "Invoice has no Purchase Order"

            return

        po = (
            db.query(PurchaseOrder)
            .filter(
                PurchaseOrder.id
                == payable.purchase_order_id
            )
            .first()
        )

        if po is None:

            payable.match_status = "PO_NOT_FOUND"

            payable.matched = False

            return

        receipts = (
            db.query(GoodsReceipt)
            .filter(
                GoodsReceipt.purchase_order_id
                == po.id
            )
            .all()
        )

        if not receipts:

            payable.match_status = "NO_RECEIPT"

            payable.match_note = "Goods not received"

            payable.matched = False

            return

        received_total = Decimal("0")

        for gr in receipts:

            for item in gr.items:

                received_total += (
                    item.quantity
                    * item.unit_cost
                )

        po_total = po.total_amount

        invoice_total = payable.amount

        if invoice_total > po_total:

            payable.match_status = "OVER_INVOICE"

            payable.match_note = (
                "Invoice exceeds Purchase Order"
            )

            payable.matched = False

            return

        tolerance = Decimal("0.02")

        difference = abs(
            invoice_total
            - received_total
        )

        if difference > (received_total * tolerance):

            payable.match_status = "PRICE_MISMATCH"

            payable.match_note = (
                "Invoice differs from received goods"
            )

            payable.matched = False

            return

        payable.match_status = "MATCHED"

        payable.match_note = "Invoice verified"

        payable.matched = True
