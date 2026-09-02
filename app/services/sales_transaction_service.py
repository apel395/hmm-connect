from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.dependencies.authorization import has_permission
from app.models.chart_of_account import ChartOfAccount
from app.models.inventory import Inventory
from app.models.location import Location
from app.models.product import Product
from app.models.stock_movement import StockMovement
from app.models.sales_transaction import SalesTransaction, SalesTransactionLine
from app.models.user import User
from app.models.warehouse import Warehouse
from app.schemas.sales_transaction import (
    SalesTransactionCreate,
    SalesTransactionItemIn,
    SalesTransactionPost,
    SalesTransactionVoid,
)
from app.services.activity_service import ActivityService
from app.services.direct_coa_service import DirectCoaService
from app.services.document_number import next_document_number
from app.services.general_ledger import GeneralLedgerService
from app.services.location_access import apply_warehouse_scope
from app.services.organization_dimensions import validate_dimensions
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine

ZERO = Decimal("0")
MONEY = Decimal("0.01")

PAYMENT_ACCOUNT_SETTINGS = {
    "CASH": "POS_CASH_ACCOUNT",
    "CARD": "POS_CARD_ACCOUNT",
    "BANK_TRANSFER": "POS_TRANSFER_ACCOUNT",
}


class SalesTransactionService:
    @staticmethod
    def _require(user: User, permission_code: str) -> None:
        if not has_permission(user, permission_code):
            raise HTTPException(403, f"{permission_code} permission required")

    @staticmethod
    def _get(db: Session, transaction_id: int, *, lock: bool = False) -> SalesTransaction:
        query = db.query(SalesTransaction).filter(SalesTransaction.id == transaction_id)
        query = query.with_for_update() if lock else query
        row = query.first()
        if not row:
            raise HTTPException(404, "POS sale not found")
        return row

    @staticmethod
    def _scoped_warehouse(db: Session, warehouse_id: int, user: User) -> Warehouse:
        warehouse = (
            apply_warehouse_scope(db.query(Warehouse), user)
            .filter(Warehouse.id == warehouse_id, Warehouse.is_active.is_(True))
            .first()
        )
        if not warehouse:
            raise HTTPException(404, "Active warehouse not found or outside your scope")
        if warehouse.location_id is None:
            raise HTTPException(409, "Warehouse must be assigned to a work location")
        return warehouse

    @staticmethod
    def _dimensions(db: Session, warehouse: Warehouse, data) -> tuple[int, int, int | None]:
        location: Location | None = db.get(Location, data.location_id or warehouse.location_id)
        if not location or not location.is_active:
            raise HTTPException(422, "Active Location is required for a POS sale")
        if warehouse.location_id != location.id:
            raise HTTPException(
                422,
                f"Warehouse {warehouse.code} belongs to Location {warehouse.location_id}, "
                "not the selected sale Location",
            )
        business_unit_id = data.business_unit_id or location.business_unit_id
        if not business_unit_id:
            raise HTTPException(422, "Selected Location is not assigned to a Business Unit")
        department_id = data.department_id
        validate_dimensions(db, business_unit_id, location.id, department_id, False)
        return business_unit_id, location.id, department_id

    @staticmethod
    def _discount(subtotal: Decimal, discount: Decimal) -> Decimal:
        if discount < ZERO:
            raise HTTPException(422, "Discount cannot be negative")
        return min(Decimal(discount or 0), Decimal(subtotal or 0))

    @classmethod
    def _materialize_items(
        cls,
        db: Session,
        transaction: SalesTransaction,
        *,
        incoming: list[SalesTransactionItemIn],
    ) -> list[SalesTransactionLine]:
        seen: set[int] = set()
        materialized: list[SalesTransactionLine] = []
        for index, line in enumerate(incoming, start=1):
            if line.product_id in seen:
                raise HTTPException(400, f"Duplicate product {line.product_id} in sale items")
            seen.add(line.product_id)
            product = db.get(Product, line.product_id)
            if not product or not product.is_active:
                raise HTTPException(404, f"Active product {line.product_id} not found")
            inventory = (
                db.query(Inventory)
                .filter(
                    Inventory.warehouse_id == transaction.warehouse_id,
                    Inventory.product_id == line.product_id,
                )
                .first()
            )
            quantity = Decimal(line.quantity)
            unit_price = (
                Decimal(line.unit_price)
                if line.unit_price is not None
                else Decimal(product.selling_price or 0)
            )
            if unit_price < ZERO:
                raise HTTPException(400, f"Unit price for {product.code} cannot be negative")
            tax_rate = Decimal(product.tax_rate or 0) if product.is_taxable else ZERO
            gross = quantity * unit_price
            tax_amount = (gross * tax_rate / Decimal("100")).quantize(MONEY) if tax_rate > 0 else ZERO
            materialized.append(
                SalesTransactionLine(
                    product_id=product.id,
                    line_number=index,
                    quantity=quantity,
                    unit_price=unit_price,
                    tax_rate=tax_rate,
                    tax_amount=tax_amount,
                    line_amount=gross,
                    unit_cost=Decimal(inventory.average_cost or 0) if inventory else ZERO,
                    uom=product.uom,
                )
            )
        return materialized

    @staticmethod
    def _totals(lines: list[SalesTransactionLine], discount: Decimal) -> dict:
        subtotal = sum((Decimal(line.line_amount or 0) for line in lines), ZERO)
        discount = min(discount, subtotal)
        tax_amount = sum((Decimal(line.tax_amount or 0) for line in lines), ZERO)
        total = (subtotal - discount + tax_amount).quantize(MONEY)
        return {
            "subtotal": subtotal,
            "discount": discount,
            "tax_amount": tax_amount,
            "total": total,
        }

    @classmethod
    def create(cls, db: Session, *, data: SalesTransactionCreate, user: User) -> SalesTransaction:
        cls._require(user, "pos.sell")
        warehouse = cls._scoped_warehouse(db, data.warehouse_id, user)
        business_unit_id, location_id, department_id = cls._dimensions(db, warehouse, data)
        transaction = SalesTransaction(
            transaction_number=next_document_number(db, "POS", digits=5, day=True),
            status="DRAFT",
            sale_date=data.sale_date or date.today(),
            warehouse_id=warehouse.id,
            customer_id=data.customer_id,
            business_unit_id=business_unit_id,
            location_id=location_id,
            department_id=department_id,
            notes=data.notes,
            created_by_id=user.id,
        )
        if data.items:
            transaction.lines = cls._materialize_items(db, transaction, incoming=data.items)
            totals = cls._totals(transaction.lines, ZERO)
            transaction.subtotal = totals["subtotal"]
            transaction.tax_amount = totals["tax_amount"]
            transaction.total_amount = totals["total"]
        db.add(transaction)
        db.flush()
        ActivityService.log(
            db=db,
            user=user,
            action="CREATE",
            entity_type="SALES_TRANSACTION",
            entity_id=transaction.id,
            summary=f"Created {transaction.transaction_number}",
            document_type="POS",
            document_number=transaction.transaction_number,
            document_status=transaction.status,
            reference_document=warehouse.code,
            details={"warehouse_id": warehouse.id, "item_count": len(transaction.lines)},
        )
        db.commit()
        db.refresh(transaction)
        return transaction

    @classmethod
    def update(
        cls,
        db: Session,
        *,
        transaction: SalesTransaction,
        data: SalesTransactionUpdate,
        user: User,
    ) -> SalesTransaction:
        cls._require(user, "pos.sell")
        if transaction.status != "DRAFT":
            raise HTTPException(409, "Only draft POS sales can be edited")
        if data.sale_date is not None:
            transaction.sale_date = data.sale_date
        if data.customer_id is not None:
            transaction.customer_id = data.customer_id
        if data.notes is not None:
            transaction.notes = data.notes
        transaction.lines = cls._materialize_items(db, transaction, incoming=data.items)
        totals = cls._totals(transaction.lines, ZERO)
        transaction.subtotal = totals["subtotal"]
        transaction.tax_amount = totals["tax_amount"]
        transaction.total_amount = totals["total"]
        ActivityService.log(
            db=db,
            user=user,
            action="UPDATE",
            entity_type="SALES_TRANSACTION",
            entity_id=transaction.id,
            summary=f"Updated {transaction.transaction_number}",
            document_type="POS",
            document_number=transaction.transaction_number,
            document_status=transaction.status,
            details={"item_count": len(transaction.lines)},
        )
        db.commit()
        db.refresh(transaction)
        return transaction

    @staticmethod
    def _debit_account(db: Session, account: ChartOfAccount | None, label: str) -> ChartOfAccount:
        if account is None:
            raise HTTPException(409, f"{label} requires an active direct COA mapping")
        if account.account_type != "ASSET" or account.normal_balance != "DEBIT":
            raise HTTPException(409, f"{label} must be a debit-balance asset account")
        return account

    @staticmethod
    def _revenue_account(db: Session, account: ChartOfAccount | None) -> ChartOfAccount:
        if account is None:
            raise HTTPException(409, "Sales revenue requires an active direct COA mapping")
        if account.account_type not in {"REVENUE", "INCOME"} or account.normal_balance != "CREDIT":
            raise HTTPException(409, "Sales revenue COA must be a credit-balance revenue account")
        return account

    @staticmethod
    def _tax_account(db: Session, account: ChartOfAccount | None) -> ChartOfAccount | None:
        if account is None:
            return None
        if account.account_type != "LIABILITY" or account.normal_balance != "CREDIT":
            raise HTTPException(409, "Output VAT COA must be a credit-balance liability account")
        return account

    @classmethod
    def _cogs_account(cls, db: Session, product: Product) -> ChartOfAccount:
        if product.cogs_account_id:
            account = db.get(ChartOfAccount, product.cogs_account_id)
            if account and account.account_type != "EXPENSE":
                account = None
            if account and account.normal_balance != "DEBIT":
                account = None
            if account:
                return account
        fallback = DirectCoaService(db).setting_account("POS_COGS_ACCOUNT", "Point of Sale COGS")
        if fallback is None:
            raise HTTPException(
                409,
                f"Item {product.code} COGS requires a direct COA mapping or a POS COGS account",
            )
        if fallback.account_type != "EXPENSE" or fallback.normal_balance != "DEBIT":
            raise HTTPException(409, "POS COGS COA must be a debit-balance expense account")
        return fallback

    @classmethod
    def post(
        cls,
        db: Session,
        *,
        transaction_id: int,
        data: SalesTransactionPost,
        user: User,
    ) -> SalesTransaction:
        cls._require(user, "pos.sell")
        transaction = cls._get(db, transaction_id, lock=True)
        if transaction.status != "DRAFT":
            raise HTTPException(409, "Only draft POS sales can be posted")
        if not transaction.lines:
            raise HTTPException(409, "POS sale has no items to post")

        subtotal = Decimal(transaction.subtotal or 0)
        discount = cls._discount(subtotal, data.discount_amount or ZERO)
        tax_amount = sum((Decimal(line.tax_amount or 0) for line in transaction.lines), ZERO)
        total = (subtotal - discount + tax_amount).quantize(MONEY)

        payment_received = Decimal(data.payment_received or ZERO)
        if data.payment_method == "CASH":
            if payment_received <= ZERO:
                raise HTTPException(422, "Cash payment requires an amount received")
            if payment_received + MONEY < total:
                raise HTTPException(422, "Cash received is less than the sale total")
            change = (payment_received - total).quantize(MONEY)
        else:
            payment_received = total
            change = ZERO

        prepared = []
        cost_total = ZERO
        for line in sorted(transaction.lines, key=lambda row: (row.product_id, row.id)):
            inventory = (
                db.query(Inventory)
                .filter(
                    Inventory.warehouse_id == transaction.warehouse_id,
                    Inventory.product_id == line.product_id,
                )
                .with_for_update()
                .first()
            )
            if not inventory:
                raise HTTPException(409, f"Inventory row for product {line.product_id} no longer exists")
            quantity = Decimal(line.quantity)
            on_hand = Decimal(inventory.quantity or 0)
            if quantity > on_hand + Decimal("0.0001"):
                raise HTTPException(
                    409,
                    f"Not enough stock for {line.product.code}: on hand {on_hand} {line.uom}, "
                    f"sale requires {quantity}",
                )
            line.unit_cost = Decimal(inventory.average_cost or 0)
            cost_total += quantity * Decimal(inventory.average_cost or 0)
            prepared.append((line, inventory))

        resolver = DirectCoaService(db)
        cash_account = cls._debit_account(
            db,
            resolver.setting_account(PAYMENT_ACCOUNT_SETTINGS[data.payment_method], f"POS {data.payment_method}"),
            f"POS {data.payment_method}",
        )
        revenue_account = cls._revenue_account(
            db, resolver.setting_account("POS_SALES_REVENUE_ACCOUNT", "POS Revenue")
        )
        tax_payable = ZERO
        if tax_amount > ZERO:
            tax_account = cls._tax_account(
                db, resolver.setting_account("POS_TAX_PAYABLE_ACCOUNT", "Output VAT Payable")
            )
            tax_payable = tax_account.id if tax_account else None

        cost_by_account: dict[int, Decimal] = {}
        inventory_by_account: dict[int, Decimal] = {}
        for line in transaction.lines:
            product = line.product or db.get(Product, line.product_id)
            cogs = cls._cogs_account(db, product)
            inv_account = resolver.inventory_account(product, transaction.location_id)
            quantity_cost = Decimal(line.quantity) * Decimal(line.unit_cost or 0)
            cost_by_account[cogs.id] = cost_by_account.get(cogs.id, ZERO) + quantity_cost
            inventory_by_account[inv_account.id] = inventory_by_account.get(inv_account.id, ZERO) + quantity_cost

        journal = JournalEntry(
            journal_number=next_document_number(db, "JV", digits=4),
            posting_date=transaction.sale_date,
            status="POSTED",
            document_type="SALES",
            document_number=transaction.transaction_number,
            reference_type="SALES_TRANSACTION",
            reference_id=transaction.id,
            description=f"Point of sale {transaction.transaction_number}",
            created_by_id=user.id,
            posted_by_id=user.id,
            business_unit_id=transaction.business_unit_id,
            location_id=transaction.location_id,
            department_id=transaction.department_id,
        )
        db.add(journal)
        db.flush()

        line_number = 1
        lines: list[tuple[int, Decimal, Decimal, str]] = []
        lines.append((cash_account.id, total, ZERO, f"Payment received {transaction.transaction_number}"))
        if tax_payable:
            lines.append((tax_payable, ZERO, tax_amount, f"Output VAT {transaction.transaction_number}"))
        lines.append((revenue_account.id, ZERO, subtotal - discount, f"Sales revenue {transaction.transaction_number}"))
        for account_id, amount in sorted(cost_by_account.items()):
            lines.append((account_id, amount, ZERO, f"Cost of goods sold {transaction.transaction_number}"))
        for account_id, amount in sorted(inventory_by_account.items()):
            lines.append((account_id, ZERO, amount, f"Inventory issued {transaction.transaction_number}"))

        total_debit = sum((debit for _, debit, _, _ in lines), ZERO)
        total_credit = sum((credit for _, _, credit, _ in lines), ZERO)
        if total_debit != total_credit:
            raise HTTPException(409, "POS journal is not balanced; contact support")

        for account_id, debit, credit, description in lines:
            journal_line = JournalLine(
                journal_entry_id=journal.id,
                account_id=account_id,
                debit=debit,
                credit=credit,
                description=description,
                business_unit_id=transaction.business_unit_id,
                department_id=transaction.department_id,
                location_id=transaction.location_id,
            )
            db.add(journal_line)
            GeneralLedgerService.post(
                db=db,
                account_id=account_id,
                debit=debit,
                credit=credit,
                posting_date=transaction.sale_date,
                journal_source="POS",
                document_type="SALES",
                document_number=transaction.transaction_number,
                reference_type="SALES_TRANSACTION",
                reference_id=transaction.id,
                reference_number=journal.journal_number,
                description=description,
                user_id=user.id,
            )

        for line, inventory in prepared:
            quantity = Decimal(line.quantity)
            inventory.quantity = Decimal(inventory.quantity or 0) - quantity
            if Decimal(inventory.quantity) == ZERO:
                inventory.average_cost = ZERO
            product = line.product or db.get(Product, line.product_id)
            cogs = cls._cogs_account(db, product)
            inv_account = resolver.inventory_account(product, transaction.location_id)
            db.add(
                StockMovement(
                    product_id=line.product_id,
                    warehouse_id=transaction.warehouse_id,
                    business_unit_id=transaction.business_unit_id,
                    location_id=transaction.location_id,
                    department_id=transaction.department_id,
                    movement_type="OUT",
                    quantity=quantity,
                    unit_cost=Decimal(line.unit_cost or 0),
                    reference_type="SALES_TRANSACTION",
                    reference_id=transaction.id,
                    notes=f"POS sale {transaction.transaction_number}",
                    inventory_account_id=inv_account.id,
                    offset_account_id=cogs.id,
                    journal_entry_id=journal.id,
                )
            )

        transaction.subtotal = subtotal
        transaction.discount_amount = discount
        transaction.tax_amount = tax_amount
        transaction.total_amount = total
        transaction.payment_method = data.payment_method
        transaction.payment_received = payment_received
        transaction.change_amount = change
        transaction.status = "POSTED"
        transaction.posted_at = datetime.now(timezone.utc)
        transaction.posted_by_id = user.id
        transaction.journal_entry_id = journal.id
        ActivityService.log(
            db=db,
            user=user,
            action="POST",
            entity_type="SALES_TRANSACTION",
            entity_id=transaction.id,
            summary=f"Posted {transaction.transaction_number}",
            document_type="POS",
            document_number=transaction.transaction_number,
            document_status=transaction.status,
            details={
                "payment_method": data.payment_method,
                "total": str(total),
                "journal_number": journal.journal_number,
            },
        )
        db.commit()
        db.refresh(transaction)
        return transaction

    @classmethod
    def void(
        cls,
        db: Session,
        *,
        transaction_id: int,
        data: SalesTransactionVoid,
        user: User,
    ) -> SalesTransaction:
        cls._require(user, "pos.sell")
        transaction = cls._get(db, transaction_id, lock=True)
        if transaction.status == "POSTED":
            raise HTTPException(
                409,
                "Posted POS sales cannot be voided; use a reversing entry to correct posted sales",
            )
        if transaction.status == "VOID":
            raise HTTPException(409, "POS sale is already voided")
        transaction.status = "VOID"
        transaction.void_reason = data.reason
        transaction.voided_at = datetime.now(timezone.utc)
        transaction.voided_by_id = user.id
        ActivityService.log(
            db=db,
            user=user,
            action="VOID",
            entity_type="SALES_TRANSACTION",
            entity_id=transaction.id,
            summary=f"Voided {transaction.transaction_number}",
            document_type="POS",
            document_number=transaction.transaction_number,
            document_status=transaction.status,
            details={"reason": data.reason},
        )
        db.commit()
        db.refresh(transaction)
        return transaction