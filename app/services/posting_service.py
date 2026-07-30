from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.account_payable import AccountPayable
from app.models.goods_receipt import GoodsReceipt
from app.models.payment import Payment
from app.models.purchase_order import PurchaseOrder
from app.models.user import User

from app.schemas.journal import (
    JournalCreate,
    JournalLineCreate,
)

from app.services.journal_service import JournalService


class PostingService:
    """
    Temporary implementation for demo.

    Account IDs are hardcoded for now.
    After the demo these will come from Accounting Settings.
    """

    CASH_ACCOUNT = 1000
    INVENTORY_ACCOUNT = 1100
    ACCOUNT_RECEIVABLE = 1200
    ACCOUNT_PAYABLE = 2100
    PURCHASE_EXPENSE = 5100

    @classmethod
    def post_goods_receipt(
        cls,
        *,
        db: Session,
        goods_receipt: GoodsReceipt,
        purchase_order: PurchaseOrder,
        payable: AccountPayable,
        destination_type: str,
        user: User,
    ):
        amount = Decimal(payable.amount)

        debit_account = (
            cls.INVENTORY_ACCOUNT
            if destination_type == "INVENTORY"
            else cls.PURCHASE_EXPENSE
        )

        JournalService.post(
            db=db,
            user=user,
            journal=JournalCreate(
                posting_date=goods_receipt.received_at.date(),
                document_type="GOODS_RECEIPT",
                document_number=goods_receipt.receipt_number,
                reference_type="GOODS_RECEIPT",
                reference_id=goods_receipt.id,
                description=f"Goods Receipt {goods_receipt.receipt_number}",
                lines=[
                    JournalLineCreate(
                        account_id=debit_account,
                        debit=amount,
                        credit=Decimal("0.00"),
                        description="Goods Receipt",
                    ),
                    JournalLineCreate(
                        account_id=cls.ACCOUNT_PAYABLE,
                        debit=Decimal("0.00"),
                        credit=amount,
                        description="Accounts Payable",
                    ),
                ],
            ),
        )

    @classmethod
    def post_supplier_payment(
        cls,
        *,
        db: Session,
        payment: Payment,
        payable: AccountPayable,
        user: User,
    ):
        JournalService.post(
            db=db,
            user=user,
            journal=JournalCreate(
                posting_date=payment.payment_date,
                document_type="PAYMENT",
                document_number=payment.payment_number,
                reference_type="PAYMENT",
                reference_id=payment.id,
                description=f"Supplier Payment {payment.payment_number}",
                lines=[
                    JournalLineCreate(
                        account_id=cls.ACCOUNT_PAYABLE,
                        debit=payment.amount,
                        credit=Decimal("0.00"),
                        description="Accounts Payable",
                    ),
                    JournalLineCreate(
                        account_id=cls.CASH_ACCOUNT,
                        debit=Decimal("0.00"),
                        credit=payment.amount,
                        description="Cash / Bank",
                    ),
                ],
            ),
        )

    @classmethod
    def post_customer_payment(
        cls,
        *,
        db: Session,
        payment,
        receivable,
        user,
    ):
        JournalService.post(
            db=db,
            user=user,
            journal=JournalCreate(
                posting_date=payment.payment_date,
                document_type="CUSTOMER_PAYMENT",
                document_number=payment.payment_number,
                reference_type="CUSTOMER_PAYMENT",
                reference_id=payment.id,
                description=f"Customer Payment {payment.payment_number}",
                lines=[
                    JournalLineCreate(
                        account_id=cls.CASH_ACCOUNT,
                        debit=payment.amount,
                        credit=Decimal("0.00"),
                        description="Cash / Bank",
                    ),
                    JournalLineCreate(
                        account_id=cls.ACCOUNT_RECEIVABLE,
                        debit=Decimal("0.00"),
                        credit=payment.amount,
                        description="Accounts Receivable",
                    ),
                ],
            ),
        )