from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.dependencies.authorization import has_permission
from app.models.chart_of_account import ChartOfAccount
from app.models.location import Location
from app.models.product import Product
from app.models.sales_transaction import SalesTransaction, SalesTransactionLine
from app.models.user import User
from app.models.warehouse import Warehouse
from app.schemas.sales_transaction import (
    SalesTransactionCreate,
    SalesTransactionItemIn,
    SalesTransactionPost,
    SalesTransactionUpdate,
    SalesTransactionVoid,
)
from app.services.ar_invoice_service import invoice_party, create_receivable
from app.services.pos_tax import pbjt_account, tax_profile
from app.services.pos_revenue import validate_revenue
from app.services.activity_service import ActivityService
from app.services.direct_coa_service import DirectCoaService
from app.services.document_number import next_document_number
from app.services.general_ledger import GeneralLedgerService
from app.services.location_access import apply_warehouse_scope, resolve_location_id, require_location_access
from app.models.business_unit import BusinessUnit
from app.services.organization_dimensions import validate_dimensions
from app.services.organization_access import business_unit_scope, department_scope, resolve_organization_access
from app.services.location_access import apply_location_scope
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
    def scoped_query(db, user):
        query = apply_location_scope(db.query(SalesTransaction), SalesTransaction.location_id, user)
        unit = business_unit_scope(db, user)
        department = department_scope(user)
        if unit is not None:
            query = query.filter(SalesTransaction.business_unit_id == unit)
        if department is not None:
            query = query.filter(SalesTransaction.department_id == department)
        return query

    @staticmethod
    def _get(db: Session, transaction_id: int, *, lock: bool = False, user=None) -> SalesTransaction:
        query = SalesTransactionService.scoped_query(db, user).filter(SalesTransaction.id == transaction_id)
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

    @classmethod
    def _master_dimensions(cls, db, data):
        from app.services import item_departments
        products = [db.get(Product, line.product_id) for line in data.items]
        if any(not p or p.item_type != "SELL" or not p.is_active for p in products):
            raise HTTPException(422, "Choose active SELL Item Master items")
        owners = item_departments.payloads(db, [p.id for p in products])
        update = {}
        for field, values in (
            ("location_id", {p.sales_location_id for p in products if p.sales_location_id}),
            ("business_unit_id", {p.sales_business_unit_id for p in products if p.sales_business_unit_id}),
            ("department_id", {owners[p.id]["department_id"] for p in products if p.id in owners}),
        ):
            if len(values) > 1:
                raise HTTPException(422, "Menus from different sales locations, business units or departments require separate orders")
            if values:
                value = next(iter(values))
                if getattr(data, field) not in (None, value):
                    raise HTTPException(422, "Order sales context must follow SELL Item Master")
                update[field] = value
        return data.model_copy(update=update)

    @staticmethod
    def _dimensions(db: Session, warehouse: Warehouse | None, data, user=None) -> tuple[int, int, int | None]:
        location_id = resolve_location_id(user, data.location_id or (warehouse.location_id if warehouse else None))
        location = db.get(Location, location_id) if location_id else None
        if not location or not location.is_active:
            raise HTTPException(422, "Select an active sales location")
        if warehouse and warehouse.location_id != location.id:
            raise HTTPException(422, "Warehouse does not belong to the sales location")
        business_unit_id = data.business_unit_id or location.business_unit_id
        if not business_unit_id:
            raise HTTPException(422, "Sales location requires a business unit")
        scope = resolve_organization_access(db, user, location_id=location.id, business_unit_id=business_unit_id, department_id=data.department_id)
        validate_dimensions(db, business_unit_id, location.id, scope["department_id"], False)
        return business_unit_id, location.id, scope["department_id"]

    @staticmethod
    def _sell_item(db, product, transaction):
        if not product or not product.is_active or product.item_type != "SELL":
            raise HTTPException(422, "POS accepts active SELL Item Master items only")
        if product.inventory_treatment != "NON_STOCK":
            raise HTTPException(422, "SELL items must use NON_STOCK treatment")
        if product.sales_location_id not in (None, transaction.location_id) or product.sales_business_unit_id not in (None, transaction.business_unit_id):
            raise HTTPException(422, "SELL item is unavailable at this sales location")
        unit = db.get(BusinessUnit, transaction.business_unit_id)
        catalog = "HOTEL" if unit and "hotel" in unit.name.casefold() else "CATERING"
        if product.catalog_type != catalog:
            raise HTTPException(422, "SELL item belongs to another item catalog")
        from app.services import item_departments
        department = item_departments.payloads(db, [product.id]).get(product.id, {}).get("department_id")
        if department is not None and department != transaction.department_id:
            raise HTTPException(422, "Choose the item's sales department / outlet")

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
            cls._sell_item(db, product, transaction)
            tax_type, tax_rate = tax_profile(product)
            tax_account = pbjt_account(db) if tax_type == "PBJT" else None
            quantity = Decimal(line.quantity)
            unit_price = (
                Decimal(line.unit_price)
                if line.unit_price is not None
                else Decimal(product.selling_price or 0)
            )
            if unit_price <= ZERO:
                raise HTTPException(400, f"Unit price for {product.code} must be greater than zero")
            gross = (quantity * unit_price).quantize(MONEY, rounding=ROUND_HALF_UP)
            tax_amount = (gross * tax_rate / Decimal("100")).quantize(MONEY, rounding=ROUND_HALF_UP) if tax_rate > 0 else ZERO
            materialized.append(
                SalesTransactionLine(
                    product_id=product.id,
                    line_number=index,
                    quantity=quantity,
                    unit_price=unit_price,
                    service_charge_rate=Decimal(product.service_charge_rate or 0),
                    service_charge_amount=(gross * Decimal(product.service_charge_rate or 0) / 100).quantize(MONEY, rounding=ROUND_HALF_UP),
                    tax_type=tax_type,
                    tax_account_id=tax_account.id if tax_account else None,
                    tax_rate=tax_rate,
                    tax_amount=tax_amount,
                    line_amount=gross,
                    unit_cost=ZERO,
                    uom=product.uom,
                )
            )
        return materialized

    @staticmethod
    def _totals(lines: list[SalesTransactionLine], discount: Decimal) -> dict:
        subtotal = sum((Decimal(line.line_amount or 0) for line in lines), ZERO)
        discount = min(discount, subtotal)
        # PBJT follows the amount charged: item value after allocated discount,
        # plus service charge. The saved rate/account are never read from the
        # current Item Master when an existing draft is posted.
        allocated = ZERO
        for index, line in enumerate(lines):
            share = ((discount * Decimal(line.line_amount or 0) / subtotal).quantize(MONEY, rounding=ROUND_HALF_UP)
                     if subtotal else ZERO)
            share = min(max(ZERO, share), discount - allocated)
            if index == len(lines) - 1:
                share = discount - allocated
            allocated += share
            if line.tax_type == "PBJT":
                base = max(ZERO, Decimal(line.line_amount or 0) - share + Decimal(line.service_charge_amount or 0))
                line.tax_amount = (base * Decimal(line.tax_rate or 0) / 100).quantize(MONEY, rounding=ROUND_HALF_UP)
        tax_amount = sum((Decimal(line.tax_amount or 0) for line in lines), ZERO)
        service_charge = sum((Decimal(getattr(line, "service_charge_amount", 0) or 0) for line in lines), ZERO)
        total = (subtotal - discount + tax_amount + service_charge).quantize(MONEY)
        return {
            "subtotal": subtotal,
            "discount": discount,
            "service_charge_amount": service_charge,
            "tax_amount": tax_amount,
            "total": total,
        }

    @classmethod
    def create(cls, db: Session, *, data: SalesTransactionCreate, user: User) -> SalesTransaction:
        cls._require(user, "pos.sell")
        if not data.warehouse_id:
            nullable = next(c["nullable"] for c in inspect(db.connection()).get_columns("sales_transactions") if c["name"] == "warehouse_id")
            if not nullable:
                raise HTTPException(503, "Apply the 20261021_pos_sell_catalog migration on EC2 before creating a location-based sale")
        data = cls._master_dimensions(db, data)
        warehouse = cls._scoped_warehouse(db, data.warehouse_id, user) if data.warehouse_id else None
        business_unit_id, location_id, department_id = cls._dimensions(db, warehouse, data, user)
        revenue = validate_revenue(db, db.get(ChartOfAccount, data.revenue_account_id), business_unit_id) if data.revenue_account_id else None
        transaction = SalesTransaction(
            revenue_account_id=revenue.id if revenue else None,
            invoice_due_date=data.invoice_due_date,
            receivable_account_id=data.receivable_account_id,
            transaction_number=next_document_number(db, "INV" if data.transaction_type == "INVOICE" else "POS", digits=5, day=True),
            status="DRAFT",
            transaction_type=data.transaction_type,
            table_number=data.table_number if data.transaction_type == "POS" else None,
            sale_date=data.sale_date or date.today(),
            warehouse_id=warehouse.id if warehouse else None,
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
            transaction.service_charge_amount = totals["service_charge_amount"]
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
            reference_document=warehouse.code if warehouse else None,
            details={"warehouse_id": warehouse.id if warehouse else None, "item_count": len(transaction.lines)},
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
        if data.invoice_due_date is not None:
            transaction.invoice_due_date=data.invoice_due_date
        if data.receivable_account_id is not None:
            transaction.receivable_account_id=data.receivable_account_id
        if data.revenue_account_id is not None:
            transaction.revenue_account_id = validate_revenue(db, db.get(ChartOfAccount, data.revenue_account_id), transaction.business_unit_id).id
        if data.sale_date is not None:
            transaction.sale_date = data.sale_date
        if data.customer_id is not None:
            transaction.customer_id = data.customer_id
        if data.notes is not None:
            transaction.notes = data.notes
        if not data.items:
            raise HTTPException(422, "A sale must contain at least one item")
        new_lines = cls._materialize_items(db, transaction, incoming=data.items)
        # The unique (sale, product) constraint still covers existing draft rows.
        # Flush their removal before inserting replacement rows for the same items.
        transaction.lines.clear()
        db.flush()
        transaction.lines = new_lines
        totals = cls._totals(transaction.lines, ZERO)
        transaction.subtotal = totals["subtotal"]
        transaction.service_charge_amount = totals["service_charge_amount"]
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
        if not account.is_active or not account.is_posting or account.account_type not in {"REVENUE", "INCOME"} or account.normal_balance != "CREDIT":
            raise HTTPException(409, "Sales revenue must use an active credit-balance revenue posting account")
        return account

    @staticmethod
    def _tax_account(db: Session, account: ChartOfAccount | None) -> ChartOfAccount | None:
        if not account or not account.is_active or not account.is_posting or account.account_type != "LIABILITY" or account.normal_balance != "CREDIT":
            raise HTTPException(409, "Sales tax COA must be an active credit-balance liability posting account")
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
        transaction = cls._get(db, transaction_id, lock=True, user=user)
        require_location_access(transaction.location_id, user)
        if transaction.status != "DRAFT":
            raise HTTPException(409, "Only draft POS sales can be posted")
        if not transaction.lines:
            raise HTTPException(409, "POS sale has no items to post")

        subtotal = Decimal(transaction.subtotal or 0)
        discount = cls._discount(subtotal, data.discount_amount or ZERO)
        totals = cls._totals(transaction.lines, discount)
        tax_amount, service_charge, total = totals["tax_amount"], totals["service_charge_amount"], totals["total"]

        is_invoice = transaction.transaction_type == "INVOICE"
        ar_account = invoice_party(db, transaction, data.customer_id, data.invoice_due_date, data.receivable_account_id) if is_invoice else None
        payment_received = Decimal(data.payment_received or ZERO)
        if is_invoice:
            payment_received=ZERO
            change=ZERO
        elif data.payment_method == "CASH":
            if payment_received <= ZERO:
                raise HTTPException(422, "Cash payment requires an amount received")
            if payment_received + MONEY < total:
                raise HTTPException(422, "Cash received is less than the sale total")
            change = (payment_received - total).quantize(MONEY)
        else:
            payment_received = total
            change = ZERO

        for line in transaction.lines:
            cls._sell_item(db, line.product or db.get(Product, line.product_id), transaction)
            if line.tax_type == "LEGACY" and any(Decimal(getattr(line.product, field, 0) or 0) > 0 for field in ("pbjt_rate", "sales_ppn_rate", "pph23_rate")):
                raise HTTPException(409, "Update this legacy draft to save its SELL tax profile before posting")
            if Decimal(line.unit_price or 0) <= ZERO:
                raise HTTPException(422, "SELL price must be greater than zero")
            line.unit_cost = ZERO

        resolver = DirectCoaService(db)
        cash_account = ar_account if is_invoice else cls._debit_account(
            db,
            resolver.setting_account(PAYMENT_ACCOUNT_SETTINGS[data.payment_method], f"POS {data.payment_method}"),
            f"POS {data.payment_method}",
        )
        revenue_id = data.revenue_account_id or transaction.revenue_account_id
        revenue_account = cls._revenue_account(db, db.get(ChartOfAccount, revenue_id) if revenue_id
            else resolver.setting_account("POS_SALES_REVENUE_ACCOUNT", "POS Revenue"))
        validate_revenue(db, revenue_account, transaction.business_unit_id)
        transaction.revenue_account_id = revenue_account.id
        tax_entries = {}
        for line in transaction.lines:
            amount = Decimal(line.tax_amount or 0)
            if amount <= ZERO:
                continue
            if line.tax_type == "PBJT":
                account = cls._tax_account(db, db.get(ChartOfAccount, line.tax_account_id) if line.tax_account_id else None)
            else:
                account = cls._tax_account(db, resolver.setting_account("POS_TAX_PAYABLE_ACCOUNT", "Output VAT Payable"))
            line.tax_account_id = account.id
            label = "PBJT" if line.tax_type == "PBJT" else "Output VAT"
            key = (account.id, label)
            tax_entries[key] = tax_entries.get(key, ZERO) + amount

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
        lines.append((cash_account.id, total, ZERO, f"{'Customer invoice receivable' if is_invoice else 'Payment received'} {transaction.transaction_number}"))
        for (account_id, label), amount in tax_entries.items():
            lines.append((account_id, ZERO, amount, f"{label} {transaction.transaction_number}"))
        lines.append((revenue_account.id, ZERO, subtotal - discount + service_charge, f"Sales revenue {transaction.transaction_number}"))
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

        transaction.subtotal = subtotal
        transaction.discount_amount = discount
        transaction.tax_amount = tax_amount
        transaction.service_charge_amount = service_charge
        transaction.total_amount = total
        transaction.payment_method = None if is_invoice else data.payment_method
        transaction.payment_received = payment_received
        transaction.change_amount = change
        transaction.status = "POSTED"
        transaction.posted_at = datetime.now(timezone.utc)
        transaction.posted_by_id = user.id
        transaction.journal_entry_id = journal.id
        if is_invoice:
            create_receivable(db, transaction, ar_account)
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
        transaction = cls._get(db, transaction_id, lock=True, user=user)
        require_location_access(transaction.location_id, user)
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
