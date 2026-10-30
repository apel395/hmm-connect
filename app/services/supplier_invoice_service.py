from datetime import datetime, timedelta, timezone
from decimal import Decimal
from collections import defaultdict
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.chart_of_account import ChartOfAccount
from app.models.goods_receipt import GoodsReceipt, GoodsReceiptItem
from app.models.journal_entry import JournalEntry
from app.services.journal_recognition import recognized_journal_filter
from app.models.journal_line import JournalLine
from app.models.purchase_order import PurchaseOrder
from app.models.supplier import Supplier
from app.models.supplier_invoice import SupplierInvoice, SupplierInvoiceLine
from app.schemas.supplier_invoice import SupplierInvoiceInput
from app.services.direct_coa_service import DirectCoaService
from app.services.audit import record_audit
from app.services.document_number import next_document_number
from app.services.location_access import enforce_location_access
from app.services.payable_balance import sync_account_payable, sync_invoice_balance

ZERO = Decimal("0")
PRICE_TOLERANCE = Decimal("0.01")


class SupplierInvoiceService:
    def _validate_fee_accounts(self, data):
        for name in ("shipping", "admin", "other"):
            amount = Decimal(getattr(data, f"{name}_fee_amount", 0) or 0)
            if not amount:
                continue
            account_id = getattr(data, f"{name}_fee_account_id", None)
            account = self.db.get(ChartOfAccount, account_id) if account_id else None
            if not account or not account.is_active or not account.is_posting or account.account_type != "EXPENSE" or account.normal_balance != "DEBIT":
                raise HTTPException(422, f"{name.title()} fee needs an active expense account")
            if name == "other" and not (getattr(data, "other_fee_description", "") or "").strip():
                raise HTTPException(422, "Other supplier charge needs a description")

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def serialize(x):
        journal = next((j for j in getattr(x, "_journals", []) if j.reference_type == "SUPPLIER_INVOICE" and j.status != "VOID"), None)
        receipt = x.goods_receipt
        purchase_order = x.purchase_order or (receipt.purchase_order if receipt else None)
        journal_location = getattr(journal, "location", None) if journal else None
        if journal and not journal_location:
            journal_location = next(
                (
                    line.location
                    for line in getattr(journal, "lines", [])
                    if getattr(line, "location", None)
                ),
                None,
            )
        location = (
            x.location
            or (receipt.location if receipt else None)
            or (
                receipt.warehouse.location
                if receipt and receipt.warehouse and receipt.warehouse.location
                else None
            )
            or (purchase_order.location if purchase_order else None)
            or journal_location
        )
        automatically_prepared = (getattr(x, "external_reference", None) or "").startswith("AUTO_RECEIPT:")
        return {
            "id": x.id,
            "internal_invoice_number": x.internal_invoice_number,
            "supplier_invoice_number": x.supplier_invoice_number,
            "auto_prepared_from_receiving": automatically_prepared,
            "supplier_reference_pending": automatically_prepared and (x.supplier_invoice_number or "").startswith("PENDING-"),
            "supplier_id": x.supplier_id,
            "supplier_name": x.supplier.name,
            "invoice_date": x.invoice_date,
            "received_date": x.received_date,
            "due_date": x.due_date,
            "purchase_order_id": x.purchase_order_id,
            "purchase_order_number": x.purchase_order.po_number if x.purchase_order else None,
            "goods_receipt_id": x.goods_receipt_id,
            "receipt_number": x.goods_receipt.receipt_number if x.goods_receipt else None,
            "business_unit_id": x.business_unit_id,
            "department_id": x.department_id,
            "department_name": x.department.name if x.department else None,
            "location_id": location.id if location else x.location_id,
            "location_name": location.name if location else None,
            "currency": x.currency,
            "subtotal": x.subtotal,
            "discount_amount": x.discount_amount,
            "tax_amount": x.tax_amount,
            "withholding_tax_amount": x.withholding_tax_amount,
            "shipping_fee_amount": x.shipping_fee_amount,
            "admin_fee_amount": x.admin_fee_amount,
            "other_fee_amount": x.other_fee_amount,
            "other_fee_description": x.other_fee_description,
            "shipping_fee_account_id": x.shipping_fee_account_id,
            "admin_fee_account_id": x.admin_fee_account_id,
            "other_fee_account_id": x.other_fee_account_id,
            "supplier_document_url": x.supplier_document_url,
            "total_amount": x.total_amount,
            "paid_amount": x.paid_amount,
            "balance_amount": x.balance_amount,
            "payment_status": x.payment_status,
            "tax_invoice_number": x.tax_invoice_number,
            "tax_invoice_date": x.tax_invoice_date,
            "status": x.status,
            "notes": x.notes,
            "source_type": x.source_type,
            "created_by_name": x.created_by.full_name if x.created_by else None,
            "created_at": x.created_at,
            "updated_at": x.updated_at,
            "verified_at": x.verified_at,
            "posted_at": x.posted_at,
            "voided_at": x.voided_at,
            "related_journal": {"id": journal.id, "journal_number": journal.journal_number, "status": journal.status} if journal else None,
            "lines": [{
                "id": line.id,
                "product_id": line.product_id,
                "product_code": line.product.code if line.product else None,
                "product_name": line.product.name if line.product else None,
                "purchase_order_item_id": line.purchase_order_item_id,
                "goods_receipt_item_id": line.goods_receipt_item_id,
                "description": line.description,
                "quantity": line.quantity,
                "uom": line.uom,
                "unit_price": line.unit_price,
                "line_amount": line.line_amount,
                "is_taxable": line.is_taxable,
                "tax_rate": line.tax_rate,
                "tax_amount": line.tax_amount,
                "account_id": line.account_id,
                "account_code": line.account.account_number if line.account else None,
                "account_name": line.account.account_name if line.account else None,
                "department_id": line.department_id,
                "notes": line.notes,
            } for line in x.lines],
        }

    def attach_journal(self, invoice):
        invoice._journals = self.db.query(JournalEntry).filter(
            JournalEntry.reference_type == "SUPPLIER_INVOICE",
            JournalEntry.reference_id == invoice.id,
        ).order_by(JournalEntry.id.desc()).all()
        return invoice

    @staticmethod
    def _source_location_id(receipt, purchase_order):
        """Resolve the authoritative work location for an invoice source.

        Warehouse receipts are anchored to the warehouse location. Direct-use
        receipts are anchored to the receipt location. PO location is only a
        legacy fallback when no receipt-specific location can be resolved.
        """
        if receipt:
            destination = str(getattr(receipt, "destination_type", "") or "").upper()
            warehouse = getattr(receipt, "warehouse", None)
            warehouse_location_id = getattr(warehouse, "location_id", None) if warehouse else None
            receipt_location_id = getattr(receipt, "location_id", None)

            if destination in {"WAREHOUSE", "MIXED"}:
                if warehouse_location_id is None:
                    raise HTTPException(
                        409,
                        "Warehouse receipt has no warehouse work location and cannot be invoiced",
                    )
                if receipt_location_id is not None and receipt_location_id != warehouse_location_id:
                    raise HTTPException(
                        409,
                        "Goods receipt location does not match its warehouse location",
                    )
                return warehouse_location_id

            # Legacy records/fixtures may predate destination_type. Preserve the
            # established resolution order: receipt, warehouse, then PO.
            if receipt_location_id is not None:
                return receipt_location_id
            if warehouse_location_id is not None:
                return warehouse_location_id

        return purchase_order.location_id if purchase_order else None

    def _receipts_for_line_ids(self, line_ids) -> list[GoodsReceipt]:
        ids={int(x) for x in line_ids if x}
        if not ids:
            return []
        items=self.db.query(GoodsReceiptItem).filter(GoodsReceiptItem.id.in_(ids)).all()
        if len(items) != len(ids):
            raise HTTPException(400, "One or more invoice receipt lines do not exist")
        receipt_ids={item.goods_receipt_id for item in items}
        return self.db.query(GoodsReceipt).filter(GoodsReceipt.id.in_(receipt_ids)).all()

    def _invoice_receipts(self, invoice: SupplierInvoice) -> list[GoodsReceipt]:
        ids={line.goods_receipt_item_id for line in invoice.lines if line.goods_receipt_item_id}
        receipts=self._receipts_for_line_ids(ids)
        if invoice.goods_receipt_id and all(r.id != invoice.goods_receipt_id for r in receipts):
            receipt=self.db.get(GoodsReceipt, invoice.goods_receipt_id)
            if receipt:
                receipts.append(receipt)
        return receipts

    @staticmethod
    def _validate_receipt_set(receipts, supplier_id, business_unit_id, location_id, department_id):
        for receipt in receipts:
            if receipt.status != "POSTED":
                raise HTTPException(409, "Supplier invoice can only use posted receipts")
            source_supplier_id=receipt.supplier_id or (receipt.purchase_order.supplier_id if receipt.purchase_order else None)
            if source_supplier_id and source_supplier_id != supplier_id:
                raise HTTPException(400, "All receipt lines on an invoice must belong to the same supplier")
            if receipt.business_unit_id != business_unit_id or receipt.location_id != location_id or receipt.department_id != department_id:
                raise HTTPException(409, "All receipt lines on an invoice must share Business Unit, Location, and Department")

    def _ensure_invoice_location(self, invoice: SupplierInvoice) -> int:
        """Resolve invoice location from its header receipt or line-level receipts."""
        purchase_order=invoice.purchase_order
        receipt=invoice.goods_receipt
        receipts=self._invoice_receipts(invoice)
        resolved=self._source_location_id(receipt, purchase_order)
        if resolved is None and receipts:
            locations={self._source_location_id(r, r.purchase_order) for r in receipts}
            if len(locations) != 1:
                raise HTTPException(409, "Supplier invoice receipt lines span multiple locations")
            resolved=locations.pop()
        if resolved is None:
            raise HTTPException(409, "Supplier invoice has no resolvable work location. Repair its source transaction before finance processing.")
        if invoice.location_id is not None and invoice.location_id != resolved:
            raise HTTPException(409, "Supplier invoice location does not match its source transaction")
        invoice.location_id=resolved
        if receipts:
            self._validate_receipt_set(receipts, invoice.supplier_id, invoice.business_unit_id, resolved, invoice.department_id)
        return resolved

    def ensure_location(self, invoice: SupplierInvoice) -> int:
        """Resolve a source-backed invoice location in the caller transaction."""
        return self._ensure_invoice_location(invoice)

    def persist_source_location(self, invoice: SupplierInvoice) -> SupplierInvoice:
        """Commit source-resolved location independently from accounting actions."""
        self._ensure_invoice_location(invoice)
        self.db.commit()
        self.db.refresh(invoice)
        return invoice

    def _inherit_source_context(self, data: SupplierInvoiceInput):
        receipt = self.db.get(GoodsReceipt, data.goods_receipt_id) if data.goods_receipt_id else None
        purchase_order = self.db.get(PurchaseOrder, data.purchase_order_id) if data.purchase_order_id else None
        if receipt:
            if receipt.status != "POSTED":
                raise HTTPException(409, "Supplier invoice can only be created from a posted receipt")
            source_supplier_id = receipt.supplier_id or (receipt.purchase_order.supplier_id if receipt.purchase_order else None)
            if source_supplier_id:
                data.supplier_id = source_supplier_id
            data.purchase_order_id = receipt.purchase_order_id
            data.business_unit_id = receipt.business_unit_id
            data.department_id = receipt.department_id
            purchase_order = receipt.purchase_order
            data.location_id = self._source_location_id(receipt, purchase_order)
        elif purchase_order:
            data.supplier_id = purchase_order.supplier_id
            data.business_unit_id = purchase_order.business_unit_id
            data.department_id = purchase_order.department_id
            data.location_id = purchase_order.location_id

        if data.location_id is None:
            raise HTTPException(
                409,
                "Supplier invoice requires a work location inherited from its source transaction",
            )
        return purchase_order, receipt

    def validate(self, data: SupplierInvoiceInput, exclude_id=None, user=None):
        from app.services.organization_dimensions import validate_dimensions

        purchase_order, receipt = self._inherit_source_context(data)
        if user is not None:
            enforce_location_access(user, data.location_id)
        validate_dimensions(self.db, data.business_unit_id, data.location_id, data.department_id, True)
        supplier = self.db.get(Supplier, data.supplier_id)
        if not supplier:
            raise HTTPException(404, "Supplier not found")

        vendor_reference = (data.supplier_invoice_number or "").strip()
        if vendor_reference:
            query = self.db.query(SupplierInvoice).filter(
                SupplierInvoice.supplier_id == data.supplier_id,
                func.lower(SupplierInvoice.supplier_invoice_number) == vendor_reference.lower(),
            )
            if exclude_id:
                query = query.filter(SupplierInvoice.id != exclude_id)
            if query.first():
                raise HTTPException(409, "Supplier reference already exists for this supplier")
        if purchase_order and purchase_order.supplier_id != data.supplier_id:
            raise HTTPException(400, "Purchase order does not belong to selected supplier")
        if receipt and receipt.purchase_order_id and purchase_order and receipt.purchase_order_id != purchase_order.id:
            raise HTTPException(400, "Receipt does not belong to selected purchase order")
        line_receipts=self._receipts_for_line_ids(line.goods_receipt_item_id for line in data.lines)
        if line_receipts:
            self._validate_receipt_set(
                line_receipts, data.supplier_id, data.business_unit_id, data.location_id, data.department_id
            )
            if receipt and any(r.id != receipt.id for r in line_receipts):
                # Multiple receipts are represented by line-level receipt links;
                # the legacy single header FK must not misrepresent the source.
                data.goods_receipt_id=None

        subtotal = sum((Decimal(line.quantity) * Decimal(line.unit_price) for line in data.lines), ZERO)
        tax_amount = (
            Decimal(data.tax_amount or 0)
            if data.source_type == "HISTORICAL_IMPORT"
            else sum((Decimal(line.tax_amount or 0) for line in data.lines), ZERO)
        )
        data.tax_amount = tax_amount
        total = subtotal - Decimal(data.discount_amount) + tax_amount - Decimal(data.withholding_tax_amount) + sum(
            (Decimal(getattr(data, f"{name}_fee_amount", 0) or 0) for name in ("shipping", "admin", "other")), ZERO)
        if Decimal(data.discount_amount) > subtotal:
            raise HTTPException(422, "Discount cannot exceed invoice goods subtotal")
        self._validate_fee_accounts(data)
        if data.total_amount is not None and Decimal(data.total_amount) != total:
            raise HTTPException(400, "Invoice total does not match line totals and adjustments")
        data.total_amount = total
        return subtotal, total

    def _previous_invoiced_quantity(self, invoice: SupplierInvoice, receipt_item_id: int) -> Decimal:
        query = self.db.query(func.coalesce(func.sum(SupplierInvoiceLine.quantity), 0)).join(
            SupplierInvoice, SupplierInvoice.id == SupplierInvoiceLine.supplier_invoice_id,
        ).filter(
            SupplierInvoiceLine.goods_receipt_item_id == receipt_item_id,
            SupplierInvoice.status.notin_({"REJECTED", "VOID"}),
        )
        if invoice.id:
            query = query.filter(SupplierInvoice.id != invoice.id)
        return Decimal(query.scalar() or 0)

    def _check_receipt_reservations(self, data: SupplierInvoiceInput, *, exclude_id: int | None = None):
        """Reserve receipt quantity while saving, not only when verifying.

        Lock receipt lines in a stable order so concurrent invoice creates for
        different supplier invoice numbers cannot both claim the last units.
        Draft/verified/posted invoices all reserve quantities; rejected and
        void invoices release them. Partial invoices remain supported.
        """
        requested = defaultdict(lambda: ZERO)
        for line in data.lines:
            if line.goods_receipt_item_id:
                requested[line.goods_receipt_item_id] += Decimal(line.quantity)
        if not requested:
            return
        items = (self.db.query(GoodsReceiptItem)
                 .filter(GoodsReceiptItem.id.in_(sorted(requested)))
                 .order_by(GoodsReceiptItem.id)
                 .with_for_update().all())
        if len(items) != len(requested):
            raise HTTPException(400, "One or more invoice receipt lines do not exist")
        for item in items:
            linked = (self.db.query(SupplierInvoice.internal_invoice_number,
                                    SupplierInvoice.status, SupplierInvoiceLine.quantity)
                      .join(SupplierInvoiceLine, SupplierInvoiceLine.supplier_invoice_id == SupplierInvoice.id)
                      .filter(SupplierInvoiceLine.goods_receipt_item_id == item.id,
                              SupplierInvoice.status.notin_(("REJECTED", "VOID"))))
            if exclude_id is not None:
                linked = linked.filter(SupplierInvoice.id != exclude_id)
            other = linked.all()
            reserved = sum((Decimal(row.quantity) for row in other), ZERO)
            available = max(ZERO, Decimal(item.quantity) - reserved)
            if requested[item.id] > available:
                drafts = sorted({row.internal_invoice_number for row in other if row.status == "DRAFT"})
                others = f" Other active drafts: {', '.join(drafts)}." if drafts else ""
                raise HTTPException(409,
                    f"Receipt line {item.id} has only {available} of {item.quantity} available; "
                    f"this invoice requests {requested[item.id]}.{others} "
                    "Open the existing draft, or reject/void an unused draft before creating another invoice.")

    @staticmethod
    def _receipt_placeholder(receipt: GoodsReceipt) -> str:
        return f"PENDING-{receipt.receipt_number}"

    @classmethod
    def is_unconfirmed_receipt_draft(cls, invoice: SupplierInvoice, receipt: GoodsReceipt) -> bool:
        """Only untouched automatic drafts can follow receiving corrections/returns."""
        if not (
            invoice.status == "DRAFT"
            and invoice.goods_receipt_id == receipt.id
            and invoice.external_reference == f"AUTO_RECEIPT:{receipt.id}"
            and invoice.supplier_invoice_number == cls._receipt_placeholder(receipt)
            and Decimal(invoice.discount_amount or 0) == ZERO
            and Decimal(invoice.withholding_tax_amount or 0) == ZERO
        ):
            return False
        source_items = {item.id: item for item in receipt.items}
        if len(invoice.lines) != len(source_items):
            return False
        linked_ids = [line.goods_receipt_item_id for line in invoice.lines]
        if len(set(linked_ids)) != len(source_items) or set(linked_ids) != set(source_items):
            return False
        return all(
            Decimal(line.quantity) == Decimal(source_items[line.goods_receipt_item_id].quantity)
            and Decimal(line.unit_price) == Decimal(source_items[line.goods_receipt_item_id].unit_cost)
            and bool(line.is_taxable) == bool(source_items[line.goods_receipt_item_id].is_taxable)
            and Decimal(line.tax_rate or 0) == Decimal(source_items[line.goods_receipt_item_id].tax_rate or 0)
            for line in invoice.lines
        )

    def prepare_receipt_draft(self, receipt: GoodsReceipt, user) -> SupplierInvoice:
        """Prepare one non-payable invoice in the same transaction as RR posting.

        The supplier's real invoice number, invoice date and tax documents are
        deliberately NOT invented. They must be confirmed before verification.
        """
        if receipt.status != "POSTED":
            raise HTTPException(409, "Receiving must be posted before preparing its invoice")
        existing = (
            self.db.query(SupplierInvoice)
            .filter(SupplierInvoice.goods_receipt_id == receipt.id,
                    SupplierInvoice.status.notin_(("VOID", "REJECTED")))
            .order_by(SupplierInvoice.id.asc())
            .with_for_update()
            .first()
        )
        if existing:
            return existing
        if not receipt.items:
            raise HTTPException(409, "Cannot prepare an invoice without receiving lines")
        receipt_item_ids = [item.id for item in receipt.items]
        already_linked = (
            self.db.query(SupplierInvoice)
            .join(SupplierInvoiceLine, SupplierInvoiceLine.supplier_invoice_id == SupplierInvoice.id)
            .filter(SupplierInvoiceLine.goods_receipt_item_id.in_(receipt_item_ids),
                    SupplierInvoice.status.notin_(("VOID", "REJECTED")))
            .first()
        )
        if already_linked:
            raise HTTPException(409, f"Receipt lines are already linked to {already_linked.internal_invoice_number}; review that invoice before preparing a new draft")

        supplier_id = receipt.supplier_id or (receipt.purchase_order.supplier_id if receipt.purchase_order else None)
        if not supplier_id:
            raise HTTPException(409, "Receiving has no supplier for invoice preparation")
        invoice_date = receipt.received_at.astimezone(ZoneInfo("Asia/Jakarta")).date() if receipt.received_at.tzinfo else receipt.received_at.date()
        invoice = SupplierInvoice(
            internal_invoice_number=next_document_number(self.db, "INV"),
            supplier_invoice_number=(receipt.supplier_invoice_number or "").strip() or self._receipt_placeholder(receipt),
            supplier_id=supplier_id,
            invoice_date=receipt.supplier_invoice_date or invoice_date,
            received_date=invoice_date,
            due_date=receipt.supplier_invoice_due_date or (invoice_date + timedelta(days=30)),
            tax_invoice_number=receipt.tax_invoice_number,
            tax_invoice_date=receipt.tax_invoice_date,
            purchase_order_id=receipt.purchase_order_id,
            goods_receipt_id=receipt.id,
            business_unit_id=receipt.business_unit_id,
            department_id=receipt.department_id,
            location_id=self._source_location_id(receipt, receipt.purchase_order),
            currency=(receipt.purchase_order.currency if receipt.purchase_order else "IDR"),
            subtotal=Decimal(receipt.subtotal),
            tax_amount=Decimal(receipt.tax_amount),
            total_amount=Decimal(receipt.total_amount),
            balance_amount=Decimal(receipt.total_amount),
            discount_amount=Decimal(receipt.discount_amount or 0),
            withholding_tax_amount=ZERO,
            shipping_fee_amount=getattr(receipt, "shipping_fee_amount", None),
            admin_fee_amount=getattr(receipt, "admin_fee_amount", None),
            other_fee_amount=getattr(receipt, "other_fee_amount", None),
            other_fee_description=getattr(receipt, "other_fee_description", None),
            shipping_fee_account_id=getattr(receipt, "shipping_fee_account_id", None),
            admin_fee_account_id=getattr(receipt, "admin_fee_account_id", None),
            other_fee_account_id=getattr(receipt, "other_fee_account_id", None),
            supplier_document_url=getattr(receipt, "supplier_document_url", None),
            status="DRAFT",
            source_type="LIVE",
            external_reference=f"AUTO_RECEIPT:{receipt.id}",
            notes=f"Prepared from {receipt.receipt_number}. Supplier document details recorded at Receiving.",
            created_by_id=user.id,
        )
        for item in receipt.items:
            invoice.lines.append(SupplierInvoiceLine(
                product_id=item.product_id,
                purchase_order_item_id=item.purchase_order_item_id,
                goods_receipt_item_id=item.id,
                description=item.product.name if item.product else f"Received product {item.product_id}",
                quantity=item.quantity,
                uom=item.product.uom if item.product else None,
                unit_price=item.unit_cost,
                line_amount=(Decimal(item.quantity) * Decimal(item.unit_cost)).quantize(Decimal("0.01")),
                is_taxable=bool(item.is_taxable),
                tax_rate=Decimal(item.tax_rate or 0),
                tax_amount=Decimal(item.tax_amount or 0),
                department_id=receipt.department_id,
            ))
        sync_invoice_balance(invoice)
        self.db.add(invoice)
        self.db.flush()
        resolver = DirectCoaService(self.db)
        for line in invoice.lines:
            resolver.snapshot_invoice_line(invoice, line)
        record_audit(self.db, user, "SUPPLIER_INVOICE_AUTO_DRAFT", "SUPPLIER_INVOICE",
                     f"Prepared {invoice.internal_invoice_number} from {receipt.receipt_number}",
                     entity_id=invoice.id)
        return invoice

    def sync_unconfirmed_receipt_draft(self, invoice: SupplierInvoice, receipt: GoodsReceipt, user) -> None:
        """Run only after confirming the draft still matches the old receipt."""
        items = {item.id: item for item in receipt.items}
        for line in invoice.lines:
            item = items[line.goods_receipt_item_id]
            line.unit_price = item.unit_cost
            line.line_amount = (Decimal(item.quantity) * Decimal(item.unit_cost)).quantize(Decimal("0.01"))
            line.tax_amount = item.tax_amount
        invoice.subtotal = receipt.subtotal
        invoice.tax_amount = receipt.tax_amount
        invoice.total_amount = receipt.total_amount
        sync_invoice_balance(invoice)
        record_audit(self.db, user, "SUPPLIER_INVOICE_AUTO_DRAFT_SYNCED", "SUPPLIER_INVOICE",
                     f"Updated provisional amounts in {invoice.internal_invoice_number} from {receipt.receipt_number}",
                     entity_id=invoice.id)

    def match_summary(self, invoice: SupplierInvoice) -> dict:
        linked_receipts=self._invoice_receipts(invoice)
        if not invoice.goods_receipt_id and not linked_receipts:
            return {
                "status": "NOT_APPLICABLE",
                "can_verify": True,
                "message": "Direct supplier invoice; three-way matching is not applicable.",
                "supplier_match": True,
                "line_count": len(invoice.lines),
                "matched_lines": len(invoice.lines),
                "issues": [],
                "lines": [],
            }

        receipt = invoice.goods_receipt
        receipts=linked_receipts or ([receipt] if receipt else [])
        purchase_order = invoice.purchase_order or (receipt.purchase_order if receipt else None)
        issues: list[str] = []
        line_results = []
        supplier_match=bool(receipts) and all(
            invoice.supplier_id == (r.supplier_id or (r.purchase_order.supplier_id if r.purchase_order else None))
            for r in receipts
        )
        if not supplier_match:
            issues.append("Supplier does not match one or more receipts.")
        if any(r.status != "POSTED" for r in receipts):
            issues.append("All goods receipts must be posted before invoice verification.")

        receipt_items={item.id:item for r in receipts for item in r.items}
        po_items={item.id:item for r in receipts if r.purchase_order for item in r.purchase_order.items}
        if purchase_order:
            po_items.update({item.id:item for item in purchase_order.items})

        for line in invoice.lines:
            receipt_item = receipt_items.get(line.goods_receipt_item_id) if line.goods_receipt_item_id else None
            if (
                invoice.source_type == "HISTORICAL_IMPORT"
                and not receipt_item
                and line.account_id
                and not line.product_id
            ):
                line_results.append({
                    "invoice_line_id": line.id,
                    "product_id": None,
                    "product_code": None,
                    "product_name": line.description,
                    "receipt_item_id": None,
                    "purchase_order_item_id": None,
                    "received_quantity": ZERO,
                    "previously_invoiced_quantity": ZERO,
                    "available_quantity": ZERO,
                    "invoice_quantity": Decimal(line.quantity),
                    "po_unit_price": None,
                    "invoice_unit_price": Decimal(line.unit_price),
                    "price_difference": None,
                    "is_taxable": line.is_taxable,
                    "tax_rate": line.tax_rate,
                    "tax_amount": line.tax_amount,
                    "reference_taxable": None,
                    "reference_tax_rate": None,
                    "uom": line.uom,
                    "reference_uom": None,
                    "status": "MATCHED",
                    "issues": [],
                })
                continue
            po_item = None
            if line.purchase_order_item_id:
                po_item = po_items.get(line.purchase_order_item_id)
            elif receipt_item and receipt_item.purchase_order_item_id:
                po_item = po_items.get(receipt_item.purchase_order_item_id)

            line_issues = []
            if not receipt_item:
                line_issues.append("Invoice line is not linked to the selected receipt line.")
            elif line.product_id and receipt_item.product_id != line.product_id:
                line_issues.append("Product does not match the receipt line.")

            received_quantity = Decimal(receipt_item.quantity) if receipt_item else ZERO
            previously_invoiced = self._previous_invoiced_quantity(invoice, receipt_item.id) if receipt_item else ZERO
            available_quantity = max(ZERO, received_quantity - previously_invoiced)
            invoice_quantity = Decimal(line.quantity)
            if receipt_item and invoice_quantity > available_quantity:
                line_issues.append(f"Invoice quantity {invoice_quantity} exceeds uninvoiced received quantity {available_quantity}.")

            po_unit_price = Decimal(po_item.unit_price) if po_item else None
            invoice_unit_price = Decimal(line.unit_price)
            price_difference = abs(invoice_unit_price - po_unit_price) if po_unit_price is not None else None
            if purchase_order and not po_item:
                line_issues.append("Receipt line is not linked to a purchase order line.")
            elif po_unit_price is not None and price_difference > PRICE_TOLERANCE:
                line_issues.append(f"Invoice unit price {invoice_unit_price} differs from PO unit price {po_unit_price}.")

            receipt_uom = po_item.uom if po_item else (receipt_item.product.uom if receipt_item and receipt_item.product else None)
            if line.uom and receipt_uom and line.uom.strip().upper() != receipt_uom.strip().upper():
                line_issues.append(f"Invoice UOM {line.uom} differs from receipt/PO UOM {receipt_uom}.")

            reference_taxable = po_item.is_taxable if po_item else (receipt_item.is_taxable if receipt_item else None)
            reference_rate = Decimal(po_item.tax_rate or 0) if po_item else (Decimal(receipt_item.tax_rate or 0) if receipt_item else None)
            # PO/receiving tax is provisional. AP confirms the supplier invoice;
            # VAT differences alone must not become a quantity/cost mismatch.

            line_results.append({
                "invoice_line_id": line.id,
                "product_id": line.product_id,
                "product_code": line.product.code if line.product else None,
                "product_name": line.product.name if line.product else line.description,
                "receipt_item_id": receipt_item.id if receipt_item else None,
                "purchase_order_item_id": po_item.id if po_item else None,
                "received_quantity": received_quantity,
                "previously_invoiced_quantity": previously_invoiced,
                "available_quantity": available_quantity,
                "invoice_quantity": invoice_quantity,
                "po_unit_price": po_unit_price,
                "invoice_unit_price": invoice_unit_price,
                "price_difference": price_difference,
                "is_taxable": line.is_taxable,
                "tax_rate": line.tax_rate,
                "tax_amount": line.tax_amount,
                "reference_taxable": reference_taxable,
                "reference_tax_rate": reference_rate,
                "uom": line.uom,
                "reference_uom": receipt_uom,
                "status": "MATCHED" if not line_issues else "MISMATCH",
                "issues": line_issues,
            })
            issues.extend(f"{line.product.name if line.product else line.description}: {issue}" for issue in line_issues)

        matched_lines = sum(1 for line in line_results if line["status"] == "MATCHED")
        status = "MATCHED" if supplier_match and not issues and len(line_results) == len(invoice.lines) else "MISMATCH"
        return {
            "status": status,
            "can_verify": status == "MATCHED",
            "message": "PO, receipt, invoice, and PPN treatment match." if status == "MATCHED" else "Resolve matching exceptions before verification.",
            "supplier_match": supplier_match,
            "line_count": len(invoice.lines),
            "matched_lines": matched_lines,
            "issues": issues,
            "lines": line_results,
        }

    def assert_match(self, invoice: SupplierInvoice):
        summary = self.match_summary(invoice)
        if not summary["can_verify"]:
            detail = summary["issues"][0] if summary["issues"] else "Three-way matching failed"
            raise HTTPException(409, f"Three-way match required: {detail}")
        return summary

    def create(self, data, user):
        subtotal, total = self.validate(data, user=user)
        self._check_receipt_reservations(data)
        generated_number = next_document_number(self.db, "INV")
        invoice = SupplierInvoice(
            internal_invoice_number=generated_number,
            supplier_invoice_number=(data.supplier_invoice_number or "").strip() or generated_number,
            supplier_id=data.supplier_id,
            invoice_date=data.invoice_date,
            received_date=data.received_date,
            due_date=data.due_date,
            purchase_order_id=data.purchase_order_id,
            goods_receipt_id=data.goods_receipt_id,
            business_unit_id=data.business_unit_id,
            department_id=data.department_id,
            location_id=data.location_id,
            currency=data.currency.upper(),
            subtotal=subtotal,
            discount_amount=data.discount_amount,
            tax_amount=data.tax_amount,
            withholding_tax_amount=data.withholding_tax_amount,
            shipping_fee_amount=data.shipping_fee_amount,
            admin_fee_amount=data.admin_fee_amount,
            other_fee_amount=data.other_fee_amount,
            other_fee_description=data.other_fee_description,
            shipping_fee_account_id=data.shipping_fee_account_id,
            admin_fee_account_id=data.admin_fee_account_id,
            other_fee_account_id=data.other_fee_account_id,
            supplier_document_url=data.supplier_document_url,
            total_amount=total,
            balance_amount=total,
            tax_invoice_number=data.tax_invoice_number,
            tax_invoice_date=data.tax_invoice_date,
            status="DRAFT",
            notes=data.notes,
            source_type=data.source_type,
            created_by_id=user.id,
        )
        for line in data.lines:
            invoice.lines.append(SupplierInvoiceLine(**line.model_dump(), line_amount=Decimal(line.quantity) * Decimal(line.unit_price)))
        sync_invoice_balance(invoice)
        self.db.add(invoice)
        self.db.flush()
        resolver = DirectCoaService(self.db)
        for invoice_line in invoice.lines:
            resolver.snapshot_invoice_line(invoice, invoice_line)
        record_audit(self.db, user, "SUPPLIER_INVOICE_CREATED", "SUPPLIER_INVOICE", f"Created {invoice.internal_invoice_number}", entity_id=invoice.id)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            constraint = getattr(getattr(exc, "orig", None), "diag", None)
            constraint_name = getattr(constraint, "constraint_name", "") or ""
            if constraint_name == "uq_supplier_invoice_supplier_number_ci":
                raise HTTPException(409, "Supplier invoice number already exists for this supplier") from exc
            raise
        self.db.refresh(invoice)
        return self.attach_journal(invoice)

    def update(self, invoice, data, user):
        if invoice.status != "DRAFT":
            raise HTTPException(409, "Only draft invoices can be edited")
        subtotal, total = self.validate(data, invoice.id, user=user)
        self._check_receipt_reservations(data, exclude_id=invoice.id)
        for key, value in data.model_dump(exclude={"lines", "total_amount"}).items():
            if key == "supplier_invoice_number":
                value = (value or "").strip() or invoice.internal_invoice_number
            setattr(invoice, key, value)
        invoice.subtotal = subtotal
        invoice.total_amount = total
        invoice.lines.clear()
        for line in data.lines:
            invoice.lines.append(SupplierInvoiceLine(**line.model_dump(), line_amount=Decimal(line.quantity) * Decimal(line.unit_price)))
        sync_invoice_balance(invoice)
        self.db.flush()
        resolver = DirectCoaService(self.db)
        for invoice_line in invoice.lines:
            resolver.snapshot_invoice_line(invoice, invoice_line)
        record_audit(self.db, user, "SUPPLIER_INVOICE_UPDATED", "SUPPLIER_INVOICE", f"Updated {invoice.internal_invoice_number}", entity_id=invoice.id)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            constraint = getattr(getattr(exc, "orig", None), "diag", None)
            constraint_name = getattr(constraint, "constraint_name", "") or ""
            if constraint_name == "uq_supplier_invoice_supplier_number_ci":
                raise HTTPException(409, "Supplier invoice number already exists for this supplier") from exc
            raise
        self.db.refresh(invoice)
        return self.attach_journal(invoice)

    def verify(self, invoice, user, *, commit: bool = True):
        invoice = (
            self.db.query(SupplierInvoice)
            .filter(SupplierInvoice.id == invoice.id)
            .populate_existing()
            .with_for_update()
            .one()
        )
        if invoice.status != "DRAFT":
            raise HTTPException(409, "Only draft invoices can be verified")
        if (
            (invoice.external_reference or "").startswith("AUTO_RECEIPT:")
            and (invoice.supplier_invoice_number or "").startswith("PENDING-")
        ):
            raise HTTPException(409, "Enter the actual supplier invoice number before verification")
        self._ensure_invoice_location(invoice)
        match = self.assert_match(invoice)

        if Decimal(invoice.tax_amount or 0) > ZERO:
            if not invoice.supplier.is_pkp:
                raise HTTPException(409, "Invoice contains PPN but supplier is not marked as PKP")
            if invoice.source_type != "HISTORICAL_IMPORT":
                if not (invoice.tax_invoice_number or "").strip():
                    raise HTTPException(409, "Tax invoice number is required for a supplier invoice containing PPN")
                if not invoice.tax_invoice_date:
                    raise HTTPException(409, "Tax invoice date is required for a supplier invoice containing PPN")

        invoice.status = "VERIFIED"
        invoice.verified_at = datetime.now(timezone.utc)
        sync_account_payable(
            self.db,
            invoice,
            matched=match["status"] in {"MATCHED", "NOT_APPLICABLE"},
            match_status=match["status"],
            match_note=match["message"],
            create_if_missing=True,
        )
        record_audit(
            self.db,
            user,
            "SUPPLIER_INVOICE_VERIFIED",
            "SUPPLIER_INVOICE",
            f"Verified {invoice.internal_invoice_number}",
            entity_id=invoice.id,
            after_data={"match_status": match["status"], "tax_amount": str(invoice.tax_amount or 0)},
        )
        if commit:
            self.db.commit()
            self.db.refresh(invoice)
        else:
            self.db.flush()
        return self.attach_journal(invoice)

    def generate_journal(self, invoice, user, *, commit: bool = True):
        invoice = (
            self.db.query(SupplierInvoice)
            .filter(SupplierInvoice.id == invoice.id)
            .populate_existing()
            .with_for_update()
            .one()
        )
        if invoice.status != "VERIFIED":
            raise HTTPException(409, "Invoice must be verified before journal generation")
        self._ensure_invoice_location(invoice)
        existing = self.db.query(JournalEntry).filter(
            JournalEntry.reference_type == "SUPPLIER_INVOICE",
            JournalEntry.reference_id == invoice.id,
            JournalEntry.status != "VOID",
        ).with_for_update().first()
        if existing and existing.status != "DRAFT":
            return existing

        resolver = DirectCoaService(self.db)
        uses_grni = resolver.receipt_uses_grni(invoice)
        linked_receipts = self._invoice_receipts(invoice) if any(
            line.goods_receipt_item_id for line in invoice.lines
        ) else []
        for receipt in linked_receipts:
            receipt_journal = self.db.query(JournalEntry.id).filter(
                JournalEntry.reference_type == "GOODS_RECEIPT",
                JournalEntry.reference_id == receipt.id,
                recognized_journal_filter(),
            ).first()
            if receipt.status != "POSTED" or receipt_journal is None:
                raise HTTPException(
                    409, f"Complete and balance the receiving journal for {receipt.receipt_number} in an open period before invoicing",
                )
        grouped = {}
        if uses_grni:
            grni_account = resolver.grni_account()
            for line in invoice.lines:
                if line.goods_receipt_item_id:
                    account = grni_account
                else:
                    account = resolver.snapshot_invoice_line(invoice, line)
                grouped[account.id] = (
                    grouped.get(account.id, ZERO)
                    + Decimal(line.line_amount or 0)
                )
        else:
            for line in invoice.lines:
                account = resolver.snapshot_invoice_line(invoice, line)
                grouped[account.id] = (
                    grouped.get(account.id, ZERO)
                    + Decimal(line.line_amount or 0)
                )

        payable_account = resolver.payable_account(invoice.supplier, invoice.location_id)
        input_vat_account = resolver.input_vat_account() if Decimal(invoice.tax_amount or 0) > ZERO else None
        discount_account = (
            resolver.purchase_discount_account()
            if Decimal(invoice.discount_amount or 0) > ZERO
            else None
        )
        withholding_account = (
            resolver.withholding_tax_payable_account()
            if Decimal(invoice.withholding_tax_amount or 0) > ZERO
            else None
        )

        journal = existing or JournalEntry(
            journal_number=next_document_number(self.db, "JV", digits=4),
            status="DRAFT", document_type="SUPPLIER_INVOICE",
            reference_type="SUPPLIER_INVOICE", reference_id=invoice.id,
            created_by_id=user.id,
        )
        if existing:
            journal.lines.clear()
            self.db.flush()
        journal.posting_date = invoice.invoice_date
        journal.document_number = invoice.internal_invoice_number
        journal.description = f"Supplier invoice {invoice.supplier_invoice_number}"
        journal.business_unit_id = invoice.business_unit_id
        journal.location_id = invoice.location_id
        journal.department_id = invoice.department_id

        line_number = 1
        for account_id, amount in grouped.items():
            journal.lines.append(JournalLine(
                line_number=line_number,
                account_id=account_id,
                debit=amount,
                credit=0,
                description=invoice.notes,
                business_unit_id=invoice.business_unit_id,
                department_id=invoice.department_id,
                location_id=invoice.location_id,
                supplier_id=invoice.supplier_id,
            ))
            line_number += 1

        if Decimal(invoice.tax_amount or 0) > ZERO:
            journal.lines.append(JournalLine(
                line_number=line_number,
                account_id=input_vat_account.id,
                debit=invoice.tax_amount,
                credit=0,
                description=f"Input VAT {invoice.tax_invoice_number}",
                business_unit_id=invoice.business_unit_id,
                department_id=invoice.department_id,
                location_id=invoice.location_id,
                supplier_id=invoice.supplier_id,
            ))
            line_number += 1

        if Decimal(invoice.discount_amount or 0) > ZERO:
            journal.lines.append(JournalLine(
                line_number=line_number,
                account_id=discount_account.id,
                debit=0,
                credit=invoice.discount_amount,
                description=f"Purchase discount {invoice.supplier_invoice_number}",
                business_unit_id=invoice.business_unit_id,
                department_id=invoice.department_id,
                location_id=invoice.location_id,
                supplier_id=invoice.supplier_id,
            ))
            line_number += 1

        if Decimal(invoice.withholding_tax_amount or 0) > ZERO:
            journal.lines.append(JournalLine(
                line_number=line_number,
                account_id=withholding_account.id,
                debit=0,
                credit=invoice.withholding_tax_amount,
                description=f"Withholding tax {invoice.supplier_invoice_number}",
                business_unit_id=invoice.business_unit_id,
                department_id=invoice.department_id,
                location_id=invoice.location_id,
                supplier_id=invoice.supplier_id,
            ))
            line_number += 1

        for kind, label in (("shipping", "Shipping"), ("admin", "Administration"), ("other", "Other")):
            amount = Decimal(getattr(invoice, f"{kind}_fee_amount", 0) or 0)
            if amount <= ZERO:
                continue
            account_id = getattr(invoice, f"{kind}_fee_account_id", None)
            account = self.db.get(ChartOfAccount, account_id) if account_id else None
            if not account or not account.is_active or not account.is_posting or account.account_type != "EXPENSE" or account.normal_balance != "DEBIT":
                raise HTTPException(409, f"{label} fee needs an active debit expense account")
            journal.lines.append(JournalLine(
                line_number=line_number, account_id=account.id, debit=amount, credit=ZERO,
                description=(invoice.other_fee_description if kind == "other" else f"{label} supplier charge"),
                business_unit_id=invoice.business_unit_id, department_id=invoice.department_id,
                location_id=invoice.location_id, supplier_id=invoice.supplier_id))
            line_number += 1

        journal.lines.append(JournalLine(
            line_number=line_number,
            account_id=payable_account.id,
            debit=0,
            credit=invoice.total_amount,
            description=f"Payable to {invoice.supplier.name}",
            business_unit_id=invoice.business_unit_id,
            department_id=invoice.department_id,
            location_id=invoice.location_id,
            supplier_id=invoice.supplier_id,
        ))

        debit_total = sum((Decimal(line.debit or 0) for line in journal.lines), ZERO)
        credit_total = sum((Decimal(line.credit or 0) for line in journal.lines), ZERO)
        if debit_total != credit_total:
            raise HTTPException(409, f"Supplier invoice journal is not balanced: debit {debit_total}, credit {credit_total}")

        self.db.add(journal)
        self.db.flush()
        record_audit(
            self.db,
            user,
            "JOURNAL_REGENERATED" if existing else "JOURNAL_GENERATED",
            "JOURNAL_ENTRY",
            f"Updated draft {journal.journal_number}" if existing else f"Generated {journal.journal_number}",
            entity_id=journal.id,
            reference_document=invoice.internal_invoice_number,
        )
        if commit:
            self.db.commit()
            self.db.refresh(journal)
        else:
            self.db.flush()
        return journal
