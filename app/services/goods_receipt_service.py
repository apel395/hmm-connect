from app.models.market_list import MarketList
from app.services.market_list_receiving import allocated_market_items
from app.services.receiving_destination import (line_destination, master_destination, resolve_destination, receipt_destination, warehouse_items)
from app.services.location_access import enforce_location_access
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from app.services.fiscal_period_service import FiscalPeriodService

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.dependencies.authorization import has_permission
from app.models.goods_receipt import GoodsReceipt, GoodsReceiptItem
from app.models.chart_of_account import ChartOfAccount
from app.models.inventory import Inventory
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.stock_movement import StockMovement
from app.models.supplier import Supplier
from app.models.supplier_invoice import SupplierInvoice, SupplierInvoiceLine
from app.models.warehouse import Warehouse
from app.schemas.goods_receipt import GoodsReceiptCostCorrection, GoodsReceiptCreate, GoodsReceiptUpdate
from app.services.activity_service import ActivityService
from app.services.document_number import next_document_number
from app.services.direct_coa_service import DirectCoaService

ZERO = Decimal("0")
MONEY = Decimal("0.01")
STOCK_CUTOFF = date(2026, 1, 1)


RECEIVING_BILLING_FIELDS = ('supplier_document_total', 'supplier_invoice_number', 'supplier_invoice_date', 'supplier_invoice_due_date', 'tax_invoice_number', 'tax_invoice_date', 'supplier_document_url', 'discount_amount', 'shipping_fee_amount', 'admin_fee_amount', 'other_fee_amount', 'other_fee_description', 'shipping_fee_account_id', 'admin_fee_account_id', 'other_fee_account_id')


class GoodsReceiptService:
    @staticmethod
    def business_date(value):
        return value.astimezone(ZoneInfo('Asia/Jakarta')).date() if value.tzinfo else value.date()

    @staticmethod
    def _number(db: Session) -> str:
        return next_document_number(db, "GR", digits=5, day=True)

    @staticmethod
    def _check_access(user, permission_code: str):
        if not has_permission(user, permission_code):
            raise HTTPException(status_code=403, detail=f"{permission_code} permission required")

    @classmethod
    def check_historical_entry(cls, db: Session, received_at: datetime | None, user):
        cls._check_access(user, "receiving.post")
        if received_at is None:
            raise HTTPException(422, "Historical entry requires a receipt date")
        business_date = received_at.astimezone(ZoneInfo("Asia/Jakarta")).date() if received_at.tzinfo else received_at.date()
        if business_date < STOCK_CUTOFF or business_date >= FiscalPeriodService.business_today():
            raise HTTPException(422, "Historical entry must be dated from 2026 and before today")
        if FiscalPeriodService.validate_posting_date(db, business_date) is None:
            raise HTTPException(409, "Configure an open accounting period for historical entry")

    @staticmethod
    def can_correct_cost(user) -> bool:
        return has_permission(user, "receiving.manage")

    @staticmethod
    def _validate_destination(db: Session, data: GoodsReceiptCreate, location_id: int | None):
        if (warehouse_items(data) if hasattr(data, "items") else data.destination_type == "WAREHOUSE"):
            if data.warehouse_id is None:
                raise HTTPException(status_code=400, detail="Warehouse is required for warehouse receiving")
            warehouse = db.get(Warehouse, data.warehouse_id)
            if not warehouse:
                raise HTTPException(status_code=404, detail="Warehouse not found")
            if location_id is None:
                raise HTTPException(status_code=409, detail="Receiving location is required for warehouse validation")
            if warehouse.location_id is None:
                raise HTTPException(status_code=409, detail="Warehouse must be assigned to a work location before receiving")
            if warehouse.location_id != location_id:
                raise HTTPException(status_code=409, detail="Warehouse must belong to the receiving work location")

    @staticmethod
    def _po_dimensions(purchase_order: PurchaseOrder):
        """Return canonical PO dimensions, repairing only uniquely resolvable legacy gaps."""
        sources = list(purchase_order.source_purchase_requisitions)
        if purchase_order.market_list is not None:
            sources.append(purchase_order.market_list)

        resolved = {}
        for field in ("business_unit_id", "location_id", "department_id"):
            current = getattr(purchase_order, field)
            if current is not None:
                resolved[field] = current
                continue
            values = {getattr(source, field) for source in sources if getattr(source, field) is not None}
            if len(values) > 1:
                label = field.removesuffix("_id").replace("_", " ")
                raise HTTPException(
                    status_code=409,
                    detail=f"Purchase order sources contain conflicting {label} values",
                )
            resolved[field] = next(iter(values), None)
            if resolved[field] is not None:
                setattr(purchase_order, field, resolved[field])
        return resolved["business_unit_id"], resolved["location_id"], resolved["department_id"]

    @staticmethod
    def _validate_item_treatments(receipt):
        for item in receipt.items:
            product = item.product
            master_destination(product)
            if line_destination(receipt, item) == "WAREHOUSE" and product.inventory_treatment in {"FIXED_ASSET", "NON_STOCK"}:
                raise HTTPException(409, f"{product.inventory_treatment} item {product.code} cannot be received into warehouse stock")

    @staticmethod
    def _receiving_debit_account(resolver, receipt, product, expense_account_id=None, destination_type=None):
        destination = destination_type or receipt.destination_type
        treatment = str(getattr(product, "inventory_treatment", "REVIEW_REQUIRED") or "REVIEW_REQUIRED").upper()
        if expense_account_id:
            if destination != "DIRECT_USE" or treatment not in {"STOCK", "DIRECT_USE", "NON_STOCK"}:
                raise HTTPException(422, "Expense destination is only available for Direct Use receiving")
            account = resolver.account(expense_account_id, "Direct Use expense destination")
            if account.account_type != "EXPENSE" or account.normal_balance != "DEBIT":
                raise HTTPException(422, "Direct Use destination must be an expense account")
            return account
        if treatment in {"STOCK", "DIRECT_USE"} and destination == "WAREHOUSE":
            return resolver.inventory_account(product, receipt.location_id)
        if treatment in {"STOCK", "DIRECT_USE", "NON_STOCK"} and destination == "DIRECT_USE":
            return resolver.expense_account(product)
        if treatment == "FIXED_ASSET" and destination == "DIRECT_USE":
            return resolver.fixed_asset_account(product)
        raise HTTPException(409, f"Item {product.code} has an incompatible receiving destination or requires inventory treatment review")

    @staticmethod
    def _validate_hotel_expenses(receipt):
        hotel_items = [item for item in receipt.items
            if line_destination(receipt, item) == "DIRECT_USE"
            and getattr(item.product, "catalog_type", "CATERING") == "HOTEL"
            and getattr(item.product, "inventory_treatment", None) != "FIXED_ASSET"]
        if hotel_items and not receipt.department_id:
            raise HTTPException(422, "Select the consuming department for Hotel Direct Use receiving")
        for item in hotel_items:
            if not item.expense_account_id:
                raise HTTPException(422, f"Choose the department expense destination for Hotel item {item.product.code}")

    @staticmethod
    def _inventory_for_update(db: Session, product_id: int, warehouse_id: int) -> Inventory:
        inventory = (
            db.query(Inventory)
            .filter(
                Inventory.product_id == product_id,
                Inventory.warehouse_id == warehouse_id,
            )
            .with_for_update()
            .first()
        )
        if inventory:
            return inventory

        if db.get_bind().dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert

            db.execute(
                insert(Inventory)
                .values(
                    product_id=product_id,
                    warehouse_id=warehouse_id,
                    quantity=ZERO,
                    average_cost=ZERO,
                )
                .on_conflict_do_nothing(
                    index_elements=[Inventory.product_id, Inventory.warehouse_id]
                )
            )
            db.flush()
            return (
                db.query(Inventory)
                .filter(
                    Inventory.product_id == product_id,
                    Inventory.warehouse_id == warehouse_id,
                )
                .with_for_update()
                .one()
            )

        inventory = Inventory(
            product_id=product_id,
            warehouse_id=warehouse_id,
            quantity=ZERO,
            average_cost=ZERO,
        )
        db.add(inventory)
        db.flush()
        return inventory

    @staticmethod
    def _movement(receipt: GoodsReceipt, receipt_item: GoodsReceiptItem, movement_type: str, reference_type: str):
        return StockMovement(
            product_id=receipt_item.product_id, warehouse_id=receipt.warehouse_id,
            goods_receipt_id=receipt.id, goods_receipt_item_id=receipt_item.id,
            purchase_order_id=receipt.purchase_order_id, purchase_order_item_id=receipt_item.purchase_order_item_id,
            business_unit_id=receipt.business_unit_id, location_id=receipt.location_id, department_id=receipt.department_id,
            movement_type=movement_type, quantity=receipt_item.quantity, unit_cost=receipt_item.unit_cost,
            reference_type=reference_type, reference_id=receipt.id,
        )

    @staticmethod
    def _tax_amount(quantity: Decimal, unit_cost: Decimal, is_taxable: bool, tax_rate: Decimal) -> Decimal:
        if not is_taxable or tax_rate <= 0:
            return ZERO
        return (quantity * unit_cost * tax_rate / Decimal("100")).quantize(MONEY, rounding=ROUND_HALF_UP)

    @classmethod
    def _recalculate_totals(cls, receipt: GoodsReceipt, db: Session | None = None) -> None:
        subtotal = ZERO
        tax = ZERO
        for item in receipt.items:
            line_subtotal = Decimal(item.quantity or 0) * Decimal(item.unit_cost or 0)
            item.tax_amount = cls._tax_amount(
                Decimal(item.quantity or 0), Decimal(item.unit_cost or 0), bool(item.is_taxable), Decimal(item.tax_rate or 0)
            )
            subtotal += line_subtotal
            tax += Decimal(item.tax_amount or 0)
        receipt.subtotal = subtotal.quantize(MONEY, rounding=ROUND_HALF_UP)
        receipt.tax_amount = tax.quantize(MONEY, rounding=ROUND_HALF_UP)
        discount = Decimal(getattr(receipt, "discount_amount", 0) or 0)
        if discount < 0 or discount > receipt.subtotal:
            raise HTTPException(422, "Invoice discount cannot exceed received subtotal")
        for name in ("shipping", "admin", "other"):
            amount = Decimal(getattr(receipt, f"{name}_fee_amount", 0) or 0)
            account_id = getattr(receipt, f"{name}_fee_account_id", None)
            if amount < 0:
                raise HTTPException(422, f"{name.title()} fee cannot be negative")
            if amount:
                account = db.get(ChartOfAccount, account_id) if db is not None and account_id else None
                if not account or not account.is_active or not account.is_posting or account.account_type != "EXPENSE" or account.normal_balance != "DEBIT":
                    raise HTTPException(422, f"{name.title()} fee requires an active debit expense account")
                if name == "other" and not (getattr(receipt, "other_fee_description", None) or "").strip():
                    raise HTTPException(422, "Describe the other supplier charge")
        fees = sum((Decimal(getattr(receipt, f"{k}_fee_amount", 0) or 0) for k in ("shipping", "admin", "other")), ZERO)
        receipt.total_amount = (receipt.subtotal + receipt.tax_amount - discount + fees).quantize(MONEY, rounding=ROUND_HALF_UP)
        if receipt.total_amount <= 0:
            raise HTTPException(422, "Total supplier invoice must be greater than zero")

    @staticmethod
    def _accounting_journal(db: Session, receipt_id: int) -> JournalEntry | None:
        return (
            db.query(JournalEntry)
            .filter(
                JournalEntry.reference_type == "GOODS_RECEIPT",
                JournalEntry.reference_id == receipt_id,
                JournalEntry.status != "VOID",
            )
            .order_by(JournalEntry.id.desc())
            .first()
        )

    @classmethod
    def _sync_accounting_journal(
        cls,
        db: Session,
        *,
        receipt: GoodsReceipt,
        user,
    ) -> JournalEntry | None:
        resolver = DirectCoaService(db)
        ap_suspense = resolver.ap_suspense_account()
        grouped: dict[int, Decimal] = {}

        for item in receipt.items:
            debit_account = cls._receiving_debit_account(resolver, receipt, item.product, getattr(item, "expense_account_id", None), line_destination(receipt, item))

            amount = (
                Decimal(item.quantity or 0) * Decimal(item.unit_cost or 0)
            ).quantize(MONEY, rounding=ROUND_HALF_UP)
            grouped[debit_account.id] = grouped.get(debit_account.id, ZERO) + amount

        subtotal = sum(grouped.values(), ZERO).quantize(
            MONEY,
            rounding=ROUND_HALF_UP,
        )
        if subtotal != Decimal(receipt.subtotal or 0):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Goods receipt accounting value does not match its subtotal: "
                    f"{subtotal} != {receipt.subtotal}"
                ),
            )

        journal = cls._accounting_journal(db, receipt.id)
        if journal and journal.status == "POSTED":
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Journal {journal.journal_number} is already posted. "
                    "Unpost it before correcting receipt accounting."
                ),
            )
        if journal is None:
            journal = JournalEntry(
                journal_number=next_document_number(db, "JV", digits=4),
                posting_date=cls.business_date(receipt.received_at),
                status="DRAFT",
                document_type="GOODS_RECEIPT",
                document_number=receipt.receipt_number,
                reference_type="GOODS_RECEIPT",
                reference_id=receipt.id,
                description=f"Goods receipt {receipt.receipt_number}",
                created_by_id=user.id,
                business_unit_id=receipt.business_unit_id,
                location_id=receipt.location_id,
                department_id=receipt.department_id,
            )
            db.add(journal)
        else:
            journal.posting_date = cls.business_date(receipt.received_at)
            journal.business_unit_id = receipt.business_unit_id
            journal.location_id = receipt.location_id
            journal.department_id = receipt.department_id
            journal.lines.clear()

        line_number = 1
        for account_id, amount in sorted(grouped.items()):
            description = f"Goods received via {receipt.receipt_number}"
            journal.lines.append(
                JournalLine(
                    line_number=line_number,
                    account_id=account_id,
                    debit=amount,
                    credit=ZERO,
                    description=description,
                    business_unit_id=receipt.business_unit_id,
                    location_id=receipt.location_id,
                    department_id=receipt.department_id,
                    supplier_id=receipt.supplier_id,
                )
            )
            line_number += 1

        journal.lines.append(
            JournalLine(
                line_number=line_number,
                account_id=ap_suspense.id,
                debit=ZERO,
                credit=subtotal,
                description=f"AP Suspense for {receipt.receipt_number}",
                business_unit_id=receipt.business_unit_id,
                location_id=receipt.location_id,
                department_id=receipt.department_id,
                supplier_id=receipt.supplier_id,
            )
        )
        return journal

    @classmethod
    def create(cls, db: Session, *, data: GoodsReceiptCreate, user):
        cls._check_access(user, "receiving.create")
        if data.source_type == "LIVE":
            data = data.model_copy(update={"received_at": datetime.now(timezone.utc)})
        if data.received_at and cls.business_date(data.received_at) < STOCK_CUTOFF:
            raise HTTPException(422, "Receiving dated before 2026 is excluded from stock")
        if data.source_type == "HISTORICAL_IMPORT":
            cls._check_access(user, "receiving.manage")
        if data.source_type == "HISTORICAL_ENTRY":
            cls.check_historical_entry(db, data.received_at, user)
        from app.services.organization_dimensions import validate_dimensions

        purchase_order = db.get(PurchaseOrder, data.purchase_order_id) if data.purchase_order_id else None
        if data.purchase_order_id:
            if not purchase_order:
                raise HTTPException(status_code=404, detail="Purchase order not found")
            if purchase_order.status not in {"APPROVED", "PARTIALLY_RECEIVED"}:
                raise HTTPException(status_code=409, detail="Only approved purchase orders can be received")
            business_unit_id, location_id, department_id = cls._po_dimensions(purchase_order)
            supplier_id = purchase_order.supplier_id
        else:
            supplier = db.get(Supplier, data.supplier_id)
            if not supplier or not supplier.is_active:
                raise HTTPException(status_code=404, detail="Active supplier not found")
            business_unit_id, location_id, department_id, supplier_id = data.business_unit_id, data.location_id, data.department_id, data.supplier_id

        market = None
        if data.market_list_id:
            market = db.query(MarketList).filter_by(id=data.market_list_id).with_for_update().first()
            if not market or market.status not in {'APPROVED', 'CONVERTED'}:
                raise HTTPException(409, 'Only approved Market Lists can be received')
            business_unit_id, location_id, department_id = market.business_unit_id, market.location_id, market.department_id
            used = allocated_market_items(db, market.id)
            sources = {line.id: line for line in market.items}
            seen_ml = set()
            for line in data.items:
                source = sources.get(line.market_list_item_id)
                if not source or line.market_list_item_id in seen_ml or source.product_id != line.product_id:
                    raise HTTPException(409, 'Invalid or duplicate Market List item')
                seen_ml.add(line.market_list_item_id)
                if line.quantity > Decimal(source.quantity)-Decimal(used.get(source.id,0)):
                    raise HTTPException(409, f'Market List item {source.id} exceeds remaining quantity')
        enforce_location_access(user, location_id)
        validate_dimensions(db, business_unit_id, location_id, department_id, True)
        receipt = GoodsReceipt(
            receipt_number=cls._number(db), status="DRAFT", purchase_order_id=purchase_order.id if purchase_order else None,
            market_list_id=market.id if market else None,
            supplier_id=supplier_id, received_by_id=user.id, received_at=data.received_at or datetime.now(timezone.utc),
            source_type=data.source_type, external_reference=data.external_reference, receipt_type=data.receipt_type,
            destination_type=data.destination_type or "DIRECT_USE", warehouse_id=data.warehouse_id,
            notes=data.notes, business_unit_id=business_unit_id, location_id=location_id, department_id=department_id,
            supplier_invoice_number=getattr(data, "supplier_invoice_number", None),
            supplier_invoice_date=getattr(data, "supplier_invoice_date", None),
            supplier_invoice_due_date=getattr(data, "supplier_invoice_due_date", None),
            tax_invoice_number=getattr(data, "tax_invoice_number", None),
            tax_invoice_date=getattr(data, "tax_invoice_date", None),
            supplier_document_url=getattr(data, "supplier_document_url", None),
            discount_amount=getattr(data, "discount_amount", None),
            shipping_fee_amount=getattr(data, "shipping_fee_amount", None),
            admin_fee_amount=getattr(data, "admin_fee_amount", None),
            other_fee_amount=getattr(data, "other_fee_amount", None),
            other_fee_description=getattr(data, "other_fee_description", None),
            shipping_fee_account_id=getattr(data, "shipping_fee_account_id", None),
            admin_fee_account_id=getattr(data, "admin_fee_account_id", None),
            other_fee_account_id=getattr(data, "other_fee_account_id", None),
        )

        seen = set()
        cost_overrides = []
        for incoming in data.items:
            if purchase_order:
                if incoming.purchase_order_item_id in seen:
                    raise HTTPException(status_code=400, detail="A PO item may appear only once per receipt")
                seen.add(incoming.purchase_order_item_id)
                po_item = db.get(PurchaseOrderItem, incoming.purchase_order_item_id)
                if not po_item or po_item.purchase_order_id != purchase_order.id:
                    raise HTTPException(status_code=400, detail="Receipt item does not belong to the purchase order")
                remaining = Decimal(po_item.quantity) - Decimal(po_item.received_quantity or 0)
                if remaining <= 0 or Decimal(incoming.quantity) > remaining:
                    raise HTTPException(status_code=409, detail=f"Quantity exceeds remaining amount for PO item {po_item.id}")
                po_cost = Decimal(po_item.unit_price or 0)
                unit_cost = Decimal(incoming.unit_cost) if incoming.unit_cost is not None else po_cost
                if incoming.unit_cost is not None and unit_cost != po_cost:
                    if not cls.can_correct_cost(user):
                        raise HTTPException(status_code=403, detail="Only an authorized manager can override PO cost during receiving")
                    if not (data.cost_correction_reason or "").strip():
                        raise HTTPException(status_code=400, detail="Correction reason is required when receiving cost differs from the PO")
                    cost_overrides.append({"purchase_order_item_id": po_item.id, "product_id": po_item.product_id, "po_unit_cost": str(po_cost), "receiving_unit_cost": str(unit_cost)})
                if unit_cost <= 0:
                    raise HTTPException(status_code=409, detail=f"Receiving unit cost must be greater than zero for PO item {po_item.id}")
                receipt.items.append(GoodsReceiptItem(
                    purchase_order_item_id=po_item.id, product_id=po_item.product_id, quantity=incoming.quantity, unit_cost=unit_cost, expense_account_id=incoming.expense_account_id,
                    destination_type=incoming.destination_type, destination_override_reason=incoming.destination_override_reason,
                    is_taxable=bool(incoming.is_taxable), tax_rate=Decimal(incoming.tax_rate or 0),
                ))
            else:
                # A supplier may deliver the same product in separate batches at
                # different prices. Keep each direct/ML receiving line intact so
                # cost, tax and downstream invoice matching remain line-specific.
                # PO and Market List source-line duplication is checked above.
                product = db.get(Product, incoming.product_id)
                if not product:
                    raise HTTPException(status_code=404, detail=f"Product {incoming.product_id} not found")
                unit_cost = Decimal(incoming.unit_cost or 0)
                if unit_cost <= 0:
                    raise HTTPException(status_code=409, detail=f"Receiving unit cost must be greater than zero for product {product.id}")
                receipt.items.append(GoodsReceiptItem(
                    purchase_order_item_id=None, market_list_item_id=incoming.market_list_item_id if market else None, product_id=product.id, quantity=incoming.quantity, unit_cost=unit_cost, expense_account_id=incoming.expense_account_id,
                    destination_type=incoming.destination_type, destination_override_reason=incoming.destination_override_reason,
                    is_taxable=bool(incoming.is_taxable), tax_rate=Decimal(incoming.tax_rate or 0),
                ))

        resolver = DirectCoaService(db)
        for line in receipt.items:
            product = db.get(Product, line.product_id)
            line.product = product
            if product.item_type != "BUY":
                raise HTTPException(422, "Receiving requires a BUY item")
            line.destination_type, line.destination_override_reason = resolve_destination(
                product, line.destination_type, line.destination_override_reason, data.destination_type,
            )
            if line.destination_type == "DIRECT_USE" and product.inventory_treatment != "FIXED_ASSET":
                line.expense_account_id = line.expense_account_id or getattr(product, "purchase_account_id", None)
            if line.expense_account_id:
                cls._receiving_debit_account(resolver, receipt, product, line.expense_account_id, line.destination_type)
        receipt.destination_type = receipt_destination(receipt)
        if not warehouse_items(receipt):
            receipt.warehouse_id = None
        cls._validate_destination(db, receipt, location_id)
        cls._validate_hotel_expenses(receipt)
        cls._recalculate_totals(receipt, db)
        db.add(receipt)
        db.flush()
        ActivityService.log(
            db=db, user=user, action="CREATE", entity_type="GOODS_RECEIPT", entity_id=receipt.id,
            summary=f"Created {receipt.receipt_number}", document_type="GR", document_number=receipt.receipt_number,
            document_status="DRAFT", reference_document=purchase_order.po_number if purchase_order else "DIRECT_RECEIPT",
            details={"source": "PO" if purchase_order else "DIRECT", "cost_overrides": cost_overrides, "line_destinations": [{"product_id": item.product_id, "destination_type": item.destination_type, "override_reason": item.destination_override_reason} for item in receipt.items], "subtotal": str(receipt.subtotal), "tax_amount": str(receipt.tax_amount), "total_amount": str(receipt.total_amount)},
        )
        db.commit(); db.refresh(receipt); return receipt

    @classmethod
    def update(cls, db: Session, *, receipt: GoodsReceipt, data: GoodsReceiptUpdate, user):
        if receipt.source_type == "LIVE":
            data = data.model_copy(update={"received_at": receipt.received_at})
        if cls.business_date(data.received_at) < STOCK_CUTOFF:
            raise HTTPException(422, "Receiving dated before 2026 is excluded from stock")
        if receipt.status != "DRAFT":
            raise HTTPException(status_code=409, detail="Only unposted Receiving Reports can be edited")

        # Receipt rows are locked by the update API; invoice creation uses the same lock.
        linked_invoice_ids = db.query(SupplierInvoiceLine.supplier_invoice_id).filter(
            SupplierInvoiceLine.goods_receipt_item_id.in_([item.id for item in receipt.items]))
        active_invoice = db.query(SupplierInvoice).filter(
            (SupplierInvoice.goods_receipt_id == receipt.id) | SupplierInvoice.id.in_(linked_invoice_ids),
            SupplierInvoice.status.notin_({"VOID", "REJECTED"})).first()
        if active_invoice:
            raise HTTPException(409, f"Resolve supplier invoice {active_invoice.internal_invoice_number} before editing its receiving source")

        from app.services.receiving_stock_cycle import draft_stock_is_clear
        if not draft_stock_is_clear(db,receipt.id):
            raise HTTPException(409, "This receiving has stock history. Use the correction/return workflow instead of draft editing")
        accounting_journal = cls._accounting_journal(db, receipt.id)
        if accounting_journal and accounting_journal.status == "POSTED":
            raise HTTPException(409, "Unpost the receiving journal and use the correction/return workflow before changing recorded items")

        for field in RECEIVING_BILLING_FIELDS:
            if field in data.model_fields_set:
                setattr(receipt, field, getattr(data, field))
        old_location_id = receipt.location_id
        if data.location_id is not None and data.location_id != receipt.location_id:
            if receipt.purchase_order_id or receipt.market_list_id:
                raise HTTPException(409, "PO and Market List receiving locations must follow their source documents")
            from app.services.organization_dimensions import validate_dimensions
            enforce_location_access(user, data.location_id)
            validate_dimensions(db, receipt.business_unit_id, data.location_id, receipt.department_id, True)
            receipt.location_id = data.location_id

        if getattr(receipt, "market_list_id", None):
            market = db.query(MarketList).filter_by(id=receipt.market_list_id).with_for_update().one()
            used = allocated_market_items(db, market.id, receipt.id)
            sources = {line.id:line for line in market.items}
            for line in data.items:
                stored = next((item for item in receipt.items if item.id == line.item_id), None)
                source = sources.get(stored.market_list_item_id) if stored else None
                if not source or line.quantity > Decimal(source.quantity)-Decimal(used.get(source.id,0)):
                    raise HTTPException(409, 'Market List quantity exceeds the remaining amount')
        purchase_order = receipt.purchase_order
        by_id = {item.id: item for item in receipt.items}
        stored_ids = {item.item_id for item in data.items if item.item_id is not None}
        new_items = [item for item in data.items if item.item_id is None]
        if stored_ids - set(by_id):
            raise HTTPException(409, "A receiving line does not belong to this report")
        removed_ids = set(by_id) - stored_ids
        # A removed line must never silently detach invoice history, including void invoices.
        if removed_ids and db.query(SupplierInvoiceLine.id).filter(
                SupplierInvoiceLine.goods_receipt_item_id.in_(removed_ids)).first():
            raise HTTPException(409, "A removed receiving line is referenced by invoice history; retain that line and use the correction/return workflow")
        if new_items and (purchase_order or receipt.market_list_id):
            raise HTTPException(409, "New lines can only be added to Direct Receiving drafts")

        changes = []
        for item_id in sorted(removed_ids):
            item = by_id[item_id]
            changes.append({"item_id": item.id, "product_id": item.product_id, "action": "REMOVE",
                "quantity": str(item.quantity), "unit_cost": str(item.unit_cost),
                "is_taxable": bool(item.is_taxable), "tax_rate": str(item.tax_rate or 0),
                "destination_type": line_destination(receipt, item), "expense_account_id": item.expense_account_id})
            receipt.items.remove(item)
        for incoming in data.items:
            if incoming.item_id is None:
                product = db.get(Product, incoming.product_id)
                if not product or not product.is_active or product.item_type != "BUY":
                    raise HTTPException(422, "New receiving lines require an active BUY item")
                destination, override_reason = resolve_destination(
                    product, incoming.destination_type, incoming.destination_override_reason,
                    data.destination_type,
                )
                expense_account_id = incoming.expense_account_id
                if destination == "DIRECT_USE" and product.inventory_treatment != "FIXED_ASSET":
                    expense_account_id = expense_account_id or getattr(product, "purchase_account_id", None)
                if expense_account_id:
                    cls._receiving_debit_account(
                        DirectCoaService(db), receipt, product, expense_account_id, destination,
                    )
                new_line = GoodsReceiptItem(
                    product_id=product.id,
                    product=product,
                    quantity=Decimal(incoming.quantity),
                    unit_cost=Decimal(incoming.unit_cost),
                    destination_type=destination,
                    destination_override_reason=override_reason,
                    expense_account_id=expense_account_id,
                    is_taxable=bool(incoming.is_taxable),
                    tax_rate=Decimal(incoming.tax_rate or 0) if incoming.is_taxable else ZERO,
                )
                receipt.items.append(new_line)
                changes.append({"product_id": product.id, "action": "ADD", "quantity": str(new_line.quantity), "unit_cost": str(new_line.unit_cost)})
                continue
            item = by_id[incoming.item_id]
            old = {
                "quantity": str(item.quantity),
                "unit_cost": str(item.unit_cost),
                "expense_account_id": item.expense_account_id,
                "destination_type": line_destination(receipt, item),
                "destination_override_reason": getattr(item, "destination_override_reason", None),
                "is_taxable": bool(item.is_taxable),
                "tax_rate": str(item.tax_rate or 0),
            }
            quantity = Decimal(incoming.quantity)
            unit_cost = Decimal(incoming.unit_cost)

            if purchase_order and item.purchase_order_item_id:
                po_item = db.get(PurchaseOrderItem, item.purchase_order_item_id)
                if not po_item or po_item.purchase_order_id != purchase_order.id:
                    raise HTTPException(status_code=409, detail=f"PO item for receipt line {item.id} is invalid")
                remaining = Decimal(po_item.quantity) - Decimal(po_item.received_quantity or 0)
                if quantity > remaining:
                    raise HTTPException(status_code=409, detail=f"Quantity exceeds remaining amount for PO item {po_item.id}")

            current_destination = line_destination(receipt, item)
            if "destination_type" in incoming.model_fields_set:
                requested = incoming.destination_type
                if requested == current_destination and incoming.destination_override_reason == getattr(item, "destination_override_reason", None):
                    # Preserve recorded/legacy routing when only cost or quantity changes.
                    item.destination_type = current_destination
                else:
                    item.destination_type, item.destination_override_reason = resolve_destination(
                        item.product, requested, incoming.destination_override_reason,
                    )
            elif data.destination_type is not None:
                item.destination_type, item.destination_override_reason = resolve_destination(item.product, legacy_header=data.destination_type)
            else:
                item.destination_type = current_destination
            item.expense_account_id = incoming.expense_account_id
            if item.destination_type == "DIRECT_USE" and item.product.inventory_treatment != "FIXED_ASSET":
                item.expense_account_id = item.expense_account_id or getattr(item.product, "purchase_account_id", None)
            if item.expense_account_id:
                cls._receiving_debit_account(DirectCoaService(db), receipt, item.product, item.expense_account_id, item.destination_type)
            item.quantity = quantity
            item.unit_cost = unit_cost
            item.is_taxable = bool(incoming.is_taxable)
            item.tax_rate = Decimal(incoming.tax_rate or 0) if incoming.is_taxable else ZERO
            new = {
                "quantity": str(item.quantity),
                "unit_cost": str(item.unit_cost),
                "expense_account_id": item.expense_account_id,
                "destination_type": line_destination(receipt, item),
                "destination_override_reason": getattr(item, "destination_override_reason", None),
                "is_taxable": bool(item.is_taxable),
                "tax_rate": str(item.tax_rate or 0),
            }
            if old != new:
                changes.append({"item_id": item.id, "before": old, "after": new})

        receipt.received_at = data.received_at
        receipt.external_reference = data.external_reference
        receipt.destination_type = receipt_destination(receipt)
        receipt.warehouse_id = data.warehouse_id if warehouse_items(receipt) else None
        cls._validate_destination(db, receipt, receipt.location_id)
        receipt.notes = data.notes
        cls._validate_hotel_expenses(receipt)
        cls._recalculate_totals(receipt, db)

        from app.services.receiving_edit_policy import reopen_approved_receiving
        reopen_approved_receiving(db, receipt, user)

        ActivityService.log(
            db=db,
            user=user,
            action="UPDATE",
            entity_type="GOODS_RECEIPT",
            entity_id=receipt.id,
            summary=f"Updated {receipt.receipt_number}",
            document_type="GR",
            document_number=receipt.receipt_number,
            document_status=receipt.status,
            reference_document=purchase_order.po_number if purchase_order else "DIRECT_RECEIPT",
            details={
                "received_at": data.received_at.isoformat(),
                "external_reference": data.external_reference,
                "destination_type": receipt.destination_type,
                "location_before_id": old_location_id,
                "location_id": receipt.location_id,
                "warehouse_id": receipt.warehouse_id,
                "notes": data.notes,
                "item_changes": changes,
                "subtotal": str(receipt.subtotal),
                "tax_amount": str(receipt.tax_amount),
                "total_amount": str(receipt.total_amount),
            },
        )
        db.commit()
        db.refresh(receipt)
        return receipt

    @classmethod
    def post(cls, db: Session, *, receipt_id: int, user):
        cls._check_access(user, "receiving.post")
        receipt = db.query(GoodsReceipt).filter(GoodsReceipt.id == receipt_id).with_for_update().first()
        if not receipt: raise HTTPException(status_code=404, detail="Goods receipt not found")
        if receipt.status != "DRAFT": raise HTTPException(status_code=409, detail="Only draft receipts can be posted")
        if receipt.source_type == "HISTORICAL_ENTRY":
            cls.check_historical_entry(db, receipt.received_at, user)
        FiscalPeriodService.validate_posting_date(db, cls.business_date(receipt.received_at))
        if cls.business_date(receipt.received_at) < STOCK_CUTOFF:
            raise HTTPException(409, "Pre-2026 receiving cannot be posted into current stock")
        if getattr(receipt, "market_list_id", None):
            market = db.query(MarketList).filter_by(id=receipt.market_list_id).with_for_update().one()
            if market.status not in {'APPROVED','CONVERTED'}:
                raise HTTPException(409, 'Market List is no longer receivable')
            used = allocated_market_items(db, market.id, receipt.id)
            sources = {item.id:item for item in market.items}
            for item in receipt.items:
                source = sources.get(item.market_list_item_id)
                if not source or item.quantity > Decimal(source.quantity)-Decimal(used.get(source.id,0)):
                    raise HTTPException(409, 'Market List quantity is no longer available')
        purchase_order = db.query(PurchaseOrder).filter(PurchaseOrder.id == receipt.purchase_order_id).with_for_update().first() if receipt.purchase_order_id else None
        if receipt.purchase_order_id and (not purchase_order or purchase_order.status not in {"APPROVED", "PARTIALLY_RECEIVED"}):
            raise HTTPException(status_code=409, detail="Purchase order is no longer receivable")
        if warehouse_items(receipt):
            warehouse = db.get(Warehouse, receipt.warehouse_id)
            if not warehouse or warehouse.location_id is None:
                raise HTTPException(status_code=409, detail="Receiving warehouse must be assigned to a work location")
            if warehouse.location_id != receipt.location_id:
                raise HTTPException(status_code=409, detail="Warehouse must belong to the receiving work location")
        if not receipt.items:
            raise HTTPException(status_code=409, detail="Goods receipt must contain at least one item before posting")
        # Serialize posting with Item Master treatment corrections and reload
        # the current setup instead of trusting a draft's cached product.
        db.query(Product).filter(Product.id.in_({i.product_id for i in receipt.items})).order_by(Product.id).populate_existing().with_for_update().all()
        cls._validate_item_treatments(receipt)
        for line in receipt.items:
            if line.product.inventory_treatment == "DIRECT_USE" and line_destination(receipt,line) == "WAREHOUSE" and not getattr(line,"destination_override_reason",None):
                raise HTTPException(409, "Item Master now uses Direct Use. Edit the receiving line or enter a warehouse exception reason before posting")
        cls._validate_hotel_expenses(receipt)
        cls._recalculate_totals(receipt, db)
        if Decimal(receipt.total_amount or 0) <= 0:
            raise HTTPException(status_code=409, detail="Goods receipt total must be greater than zero")
        for receipt_item in receipt.items:
            quantity = Decimal(receipt_item.quantity)
            if quantity <= 0: raise HTTPException(status_code=409, detail=f"Receipt item {receipt_item.id} must have positive quantity")
            if Decimal(receipt_item.unit_cost or 0) <= 0: raise HTTPException(status_code=409, detail=f"Receipt item {receipt_item.id} has zero unit cost and cannot be posted")
            if purchase_order:
                po_item = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.id == receipt_item.purchase_order_item_id, PurchaseOrderItem.purchase_order_id == purchase_order.id).with_for_update().first()
                if not po_item: raise HTTPException(status_code=409, detail=f"PO item for receipt line {receipt_item.id} no longer exists")
                remaining = Decimal(po_item.quantity) - Decimal(po_item.received_quantity or 0)
                if quantity > remaining: raise HTTPException(status_code=409, detail=f"Quantity exceeds remaining amount for PO item {po_item.id}")
                po_item.received_quantity = Decimal(po_item.received_quantity or 0) + quantity
                receipt_item.product_id = po_item.product_id
            if line_destination(receipt, receipt_item) == "WAREHOUSE":
                from app.services.receiving_stock_cycle import active_receipt_stock
                existing_movement = next((m for m in active_receipt_stock(db,receipt.id) if m.goods_receipt_item_id == receipt_item.id),None)
                if existing_movement:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            f"Receiving line {receipt_item.id} already has stock movement "
                            f"SM-{existing_movement.id:08d}; posting aborted to prevent duplicate stock."
                        ),
                    )
                inventory = cls._inventory_for_update(
                    db,
                    receipt_item.product_id,
                    receipt.warehouse_id,
                )
                old_qty, old_avg = Decimal(inventory.quantity or 0), Decimal(inventory.average_cost or 0)
                new_qty = old_qty + quantity
                inventory.average_cost = ((old_qty * old_avg) + (quantity * Decimal(receipt_item.unit_cost))) / new_qty
                inventory.quantity = new_qty
                db.add(cls._movement(receipt, receipt_item, "IN", "GOODS_RECEIPT"))

        db.flush()
        if warehouse_items(receipt):
            from app.services.receiving_stock_cycle import active_receipt_stock
            movement_count = len(active_receipt_stock(db,receipt.id))
            if movement_count != len(warehouse_items(receipt)):
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Receiving inventory ledger verification failed: expected "
                        f"{len(warehouse_items(receipt))} movements, found {movement_count}."
                    ),
                )
            missing_inventory = []
            for receipt_item in warehouse_items(receipt):
                inventory = (
                    db.query(Inventory)
                    .filter(
                        Inventory.product_id == receipt_item.product_id,
                        Inventory.warehouse_id == receipt.warehouse_id,
                    )
                    .first()
                )
                if inventory is None:
                    missing_inventory.append(receipt_item.product_id)
            if missing_inventory:
                raise HTTPException(
                    status_code=409,
                    detail=f"Receiving inventory balance verification failed for products {missing_inventory[:10]}",
                )

        journal = cls._sync_accounting_journal(db, receipt=receipt, user=user)
        if warehouse_items(receipt) and journal is not None:
            resolver = DirectCoaService(db)
            ap_suspense = resolver.ap_suspense_account()
            for movement in active_receipt_stock(db,receipt.id):
                product = db.get(Product, movement.product_id)
                movement.inventory_account_id = resolver.inventory_account(product, receipt.location_id).id
                movement.offset_account_id = ap_suspense.id
                movement.journal_entry_id = journal.id
        if purchase_order:
            purchase_order.status = "RECEIVED" if all(Decimal(item.received_quantity or 0) >= Decimal(item.quantity) for item in purchase_order.items) else "PARTIALLY_RECEIVED"
        receipt.status = "POSTED"
        if receipt.source_type != "HISTORICAL_IMPORT":
            # The RR is the source document; Finance confirms the supplier's
            # actual invoice details later. Both records commit atomically.
            from app.services.supplier_invoice_service import SupplierInvoiceService
            invoice_service = SupplierInvoiceService(db)
            invoice = invoice_service.prepare_receipt_draft(receipt, user)
            # A supplier's actual document is received with Catering goods.
            # If its required fields are complete, finalize invoice verification
            # and prepare a recognized open-period DRAFT accounting journal atomically.
            # Without real billing details, keep an editable invoice DRAFT.
            has_vendor_invoice = bool((getattr(receipt, "supplier_invoice_number", None) or "").strip() and getattr(receipt, "supplier_invoice_date", None) and getattr(receipt, "supplier_document_total", None) is not None)
            has_vat_docs = invoice is not None and (Decimal(invoice.tax_amount or 0) <= ZERO or bool(
                (getattr(receipt, "tax_invoice_number", None) or "").strip() and getattr(receipt, "tax_invoice_date", None)))
            is_catering = bool(receipt.items) and all(
                getattr(item.product, "catalog_type", None) == "CATERING" for item in receipt.items
            )
            has_matching_total = (
                invoice is not None
                and getattr(receipt, "supplier_document_total", None) is not None
                and Decimal(receipt.supplier_document_total) == Decimal(invoice.total_amount)
            )
            eligible_for_auto_verify = (
                receipt.source_type == "LIVE" and is_catering and has_vendor_invoice
                and has_vat_docs and has_matching_total
                and (Decimal(invoice.tax_amount or 0) <= ZERO or bool(invoice.supplier.is_pkp))
            )
            if eligible_for_auto_verify:
                # Incomplete source matching or accounting master data should
                # leave a correctable AP draft, never block the physical receipt.
                eligible_for_auto_verify = (
                    invoice_service.match_summary(invoice)["can_verify"]
                    and DirectCoaService(db).supplier_invoice_readiness(invoice)["is_ready"]
                )
            if eligible_for_auto_verify:
                FiscalPeriodService.validate_posting_date(db, invoice.invoice_date, system_closing=True)
                invoice_service.verify(invoice, user, commit=False)
                invoice_service.generate_journal(invoice, user, commit=False)
        ActivityService.log(db=db, user=user, action="POST", entity_type="GOODS_RECEIPT", entity_id=receipt.id, summary=f"Posted {receipt.receipt_number}", document_type="GR", document_number=receipt.receipt_number, document_status="POSTED", reference_document=purchase_order.po_number if purchase_order else "DIRECT_RECEIPT", details={"purchase_order_id": receipt.purchase_order_id, "warehouse_id": receipt.warehouse_id, "destination_type": receipt.destination_type})
        db.commit(); db.refresh(receipt); return receipt

    @classmethod
    def correct_costs(cls, db: Session, *, receipt_id: int, data: GoodsReceiptCostCorrection, user):
        if not cls.can_correct_cost(user): raise HTTPException(status_code=403, detail="Only an authorized manager can correct receiving costs")
        receipt = db.query(GoodsReceipt).filter(GoodsReceipt.id == receipt_id).with_for_update().first()
        if not receipt: raise HTTPException(status_code=404, detail="Goods receipt not found")
        if receipt.status not in {"DRAFT", "POSTED"}: raise HTTPException(status_code=409, detail="Only draft or posted receipts can have their costs corrected")
        downstream_invoice = db.query(SupplierInvoice).filter(SupplierInvoice.goods_receipt_id == receipt.id, SupplierInvoice.status.notin_({"VOID", "REJECTED"})).first()
        provisional_invoice = None
        if downstream_invoice:
            from app.services.supplier_invoice_service import SupplierInvoiceService
            if not SupplierInvoiceService.is_unconfirmed_receipt_draft(downstream_invoice, receipt):
                raise HTTPException(status_code=409, detail=f"Receiving cost cannot be corrected after supplier invoice {downstream_invoice.internal_invoice_number} has been confirmed or modified")
            provisional_invoice = downstream_invoice
        by_id = {item.id: item for item in receipt.items}; changes = []
        for correction in data.items:
            item = by_id.get(correction.item_id)
            if not item: raise HTTPException(status_code=400, detail=f"Receipt item {correction.item_id} does not belong to this receipt")
            old_cost, new_cost = Decimal(item.unit_cost or 0), Decimal(correction.unit_cost)
            if new_cost == old_cost: continue
            if receipt.status == "POSTED" and line_destination(receipt, item) == "WAREHOUSE":
                from app.services.receiving_stock_cycle import active_receipt_stock
                movement = next((m for m in active_receipt_stock(db,receipt.id) if m.goods_receipt_item_id == item.id),None)
                if not movement: raise HTTPException(status_code=409, detail=f"Original inventory movement for receipt item {item.id} was not found")
                later_outbound = db.query(StockMovement).filter(StockMovement.product_id == item.product_id, StockMovement.warehouse_id == receipt.warehouse_id, StockMovement.id > movement.id, StockMovement.movement_type == "OUT").first()
                if later_outbound: raise HTTPException(status_code=409, detail=f"Cost for product {item.product_id} cannot be corrected after stock has moved out")
                inventory = db.query(Inventory).filter(Inventory.product_id == item.product_id, Inventory.warehouse_id == receipt.warehouse_id).with_for_update().first()
                if not inventory or Decimal(inventory.quantity or 0) <= 0: raise HTTPException(status_code=409, detail=f"Current inventory for product {item.product_id} cannot be revalued")
                qty, current_qty = Decimal(item.quantity), Decimal(inventory.quantity)
                inventory.average_cost = Decimal(inventory.average_cost or 0) + (((new_cost - old_cost) * qty) / current_qty)
                movement.unit_cost = new_cost
            item.unit_cost = new_cost
            changes.append({"item_id": item.id, "product_id": item.product_id, "old_unit_cost": str(old_cost), "new_unit_cost": str(new_cost)})
        if not changes: raise HTTPException(status_code=400, detail="No receiving costs changed")
        cls._recalculate_totals(receipt, db)
        if receipt.status == "POSTED":
            cls._sync_accounting_journal(db, receipt=receipt, user=user)
        if provisional_invoice:
            SupplierInvoiceService(db).sync_unconfirmed_receipt_draft(provisional_invoice, receipt, user)
        ActivityService.log(db=db, user=user, action="COST_CORRECTION", entity_type="GOODS_RECEIPT", entity_id=receipt.id, summary=f"Corrected receiving cost for {receipt.receipt_number}", document_type="GR", document_number=receipt.receipt_number, document_status=receipt.status, reference_document=receipt.purchase_order.po_number if receipt.purchase_order else "DIRECT_RECEIPT", details={"reason": data.reason.strip(), "changes": changes, "subtotal": str(receipt.subtotal), "tax_amount": str(receipt.tax_amount), "total_amount": str(receipt.total_amount)})
        db.commit(); db.refresh(receipt); return receipt

    @classmethod
    def return_receipt(cls, db: Session, *, receipt_id: int, user):
        cls._check_access(user, "receiving.return")
        receipt = db.query(GoodsReceipt).filter(GoodsReceipt.id == receipt_id).with_for_update().first()
        if not receipt: raise HTTPException(status_code=404, detail="Goods receipt not found")
        if receipt.status != "POSTED": raise HTTPException(status_code=409, detail="Only posted receipts can be returned")
        accounting_journal = cls._accounting_journal(db, receipt.id)
        if accounting_journal and accounting_journal.status == "POSTED":
            raise HTTPException(
                status_code=409,
                detail=f"Unpost journal {accounting_journal.journal_number} before returning this receipt",
            )
        downstream_invoice = db.query(SupplierInvoice).filter(SupplierInvoice.goods_receipt_id == receipt.id, SupplierInvoice.status.notin_({"VOID", "REJECTED"})).first()
        provisional_invoice = None
        if downstream_invoice:
            from app.services.supplier_invoice_service import SupplierInvoiceService
            if not SupplierInvoiceService.is_unconfirmed_receipt_draft(downstream_invoice, receipt):
                raise HTTPException(status_code=409, detail=f"Receipt cannot be returned after supplier invoice {downstream_invoice.internal_invoice_number} has been confirmed or modified")
            provisional_invoice = downstream_invoice
        purchase_order = db.query(PurchaseOrder).filter(PurchaseOrder.id == receipt.purchase_order_id).with_for_update().first() if receipt.purchase_order_id else None
        for receipt_item in receipt.items:
            quantity = Decimal(receipt_item.quantity)
            if line_destination(receipt, receipt_item) == "WAREHOUSE":
                inventory = db.query(Inventory).filter(Inventory.product_id == receipt_item.product_id, Inventory.warehouse_id == receipt.warehouse_id).with_for_update().first()
                if not inventory or Decimal(inventory.quantity or 0) < quantity: raise HTTPException(status_code=409, detail=f"Insufficient current stock to return product {receipt_item.product_id}")
                current_qty, current_avg = Decimal(inventory.quantity or 0), Decimal(inventory.average_cost or 0)
                current_value, return_value = current_qty * current_avg, quantity * Decimal(receipt_item.unit_cost or 0)
                new_qty, remaining_value = current_qty - quantity, current_value - return_value
                if new_qty == 0: inventory.quantity, inventory.average_cost = ZERO, ZERO
                else:
                    if remaining_value < ZERO: raise HTTPException(status_code=409, detail=f"Return would make inventory value negative for product {receipt_item.product_id}")
                    inventory.quantity, inventory.average_cost = new_qty, remaining_value / new_qty
                db.add(cls._movement(receipt, receipt_item, "OUT", "GOODS_RECEIPT_RETURN"))
            if purchase_order and receipt_item.purchase_order_item_id:
                po_item = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.id == receipt_item.purchase_order_item_id).with_for_update().first()
                if not po_item: raise HTTPException(status_code=409, detail=f"PO item for receipt line {receipt_item.id} no longer exists")
                po_item.received_quantity = max(ZERO, Decimal(po_item.received_quantity or 0) - quantity)
        if purchase_order:
            purchase_order.status = "RECEIVED" if all(Decimal(item.received_quantity or 0) >= Decimal(item.quantity) for item in purchase_order.items) else "PARTIALLY_RECEIVED" if any(Decimal(item.received_quantity or 0) > 0 for item in purchase_order.items) else "APPROVED"
        receipt.status = "RETURNED"
        if provisional_invoice:
            provisional_invoice.status = "VOID"
            provisional_invoice.voided_at = datetime.now(timezone.utc)
            ActivityService.log(db=db, user=user, action="AUTO_VOID", entity_type="SUPPLIER_INVOICE", entity_id=provisional_invoice.id,
                                summary=f"Voided unconfirmed {provisional_invoice.internal_invoice_number} after returning {receipt.receipt_number}",
                                document_type="SUPPLIER_INVOICE", document_number=provisional_invoice.internal_invoice_number,
                                document_status="VOID", reference_document=receipt.receipt_number)
        if accounting_journal and accounting_journal.status == "DRAFT":
            accounting_journal.status = "VOID"
            accounting_journal.voided_at = datetime.now(timezone.utc)
        ActivityService.log(db=db, user=user, action="RETURN", entity_type="GOODS_RECEIPT", entity_id=receipt.id, summary=f"Returned {receipt.receipt_number}", document_type="GR", document_number=receipt.receipt_number, document_status="RETURNED", reference_document=purchase_order.po_number if purchase_order else "DIRECT_RECEIPT")
        db.commit(); db.refresh(receipt); return receipt
