from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.chart_of_account import ChartOfAccount
from app.models.goods_receipt import GoodsReceipt
from app.models.journal_entry import JournalEntry
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
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def serialize(x):
        journal = next((j for j in getattr(x, "_journals", []) if j.reference_type == "SUPPLIER_INVOICE"), None)
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
        return {
            "id": x.id,
            "internal_invoice_number": x.internal_invoice_number,
            "supplier_invoice_number": x.supplier_invoice_number,
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
        ).all()
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

            if destination == "WAREHOUSE":
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

    def _ensure_invoice_location(self, invoice: SupplierInvoice) -> int:
        """Repair a uniquely resolvable legacy location, otherwise block finance actions."""
        purchase_order = invoice.purchase_order
        receipt = invoice.goods_receipt
        resolved = self._source_location_id(receipt, purchase_order)

        if resolved is None:
            raise HTTPException(
                409,
                "Supplier invoice has no resolvable work location. Repair its source transaction before finance processing.",
            )

        if invoice.location_id is not None and invoice.location_id != resolved:
            raise HTTPException(
                409,
                "Supplier invoice location does not match its source transaction",
            )

        invoice.location_id = resolved
        if receipt and receipt.location_id is None:
            receipt.location_id = resolved
        if purchase_order and purchase_order.location_id is None:
            purchase_order.location_id = resolved
        return resolved

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

        query = self.db.query(SupplierInvoice).filter(
            SupplierInvoice.supplier_id == data.supplier_id,
            func.lower(SupplierInvoice.supplier_invoice_number) == data.supplier_invoice_number.strip().lower(),
        )
        if exclude_id:
            query = query.filter(SupplierInvoice.id != exclude_id)
        if query.first():
            raise HTTPException(409, "Supplier invoice number already exists for this supplier")
        if purchase_order and purchase_order.supplier_id != data.supplier_id:
            raise HTTPException(400, "Purchase order does not belong to selected supplier")
        if receipt and receipt.purchase_order_id and purchase_order and receipt.purchase_order_id != purchase_order.id:
            raise HTTPException(400, "Receipt does not belong to selected purchase order")
        if receipt:
            receipt_item_ids = {item.id for item in receipt.items}
            if any(line.goods_receipt_item_id and line.goods_receipt_item_id not in receipt_item_ids for line in data.lines):
                raise HTTPException(400, "Invoice line does not belong to selected receipt")

        subtotal = sum((Decimal(line.quantity) * Decimal(line.unit_price) for line in data.lines), ZERO)
        tax_amount = sum((Decimal(line.tax_amount or 0) for line in data.lines), ZERO)
        data.tax_amount = tax_amount
        total = subtotal - Decimal(data.discount_amount) + tax_amount - Decimal(data.withholding_tax_amount)
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

    def match_summary(self, invoice: SupplierInvoice) -> dict:
        if not invoice.goods_receipt_id:
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
        purchase_order = invoice.purchase_order or (receipt.purchase_order if receipt else None)
        issues: list[str] = []
        line_results = []
        supplier_match = bool(
            receipt
            and invoice.supplier_id == (receipt.supplier_id or (receipt.purchase_order.supplier_id if receipt.purchase_order else None))
            and (not purchase_order or invoice.supplier_id == purchase_order.supplier_id)
        )
        if not supplier_match:
            issues.append("Supplier does not match the receipt/purchase order.")
        if not receipt or receipt.status != "POSTED":
            issues.append("Goods receipt must be posted before invoice verification.")

        receipt_items = {item.id: item for item in receipt.items} if receipt else {}
        po_items = {item.id: item for item in purchase_order.items} if purchase_order else {}

        for line in invoice.lines:
            receipt_item = receipt_items.get(line.goods_receipt_item_id) if line.goods_receipt_item_id else None
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
            if reference_taxable is not None and bool(line.is_taxable) != bool(reference_taxable):
                line_issues.append("Invoice PPN applicability differs from PO/receiving tax snapshot.")
            if bool(line.is_taxable) and reference_rate is not None and Decimal(line.tax_rate or 0) != reference_rate:
                line_issues.append("Invoice PPN rate differs from PO/receiving tax snapshot.")

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
        invoice = SupplierInvoice(
            internal_invoice_number=next_document_number(self.db, "INV"),
            supplier_invoice_number=data.supplier_invoice_number.strip(),
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
        for key, value in data.model_dump(exclude={"lines", "total_amount"}).items():
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
        self._ensure_invoice_location(invoice)
        match = self.assert_match(invoice)

        if Decimal(invoice.tax_amount or 0) > ZERO:
            if not invoice.supplier.is_pkp:
                raise HTTPException(409, "Invoice contains PPN but supplier is not marked as PKP")
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
        ).first()
        if existing:
            return existing

        resolver = DirectCoaService(self.db)
        uses_grni = resolver.receipt_uses_grni(invoice)
        grouped = {}
        if uses_grni:
            grni_account = resolver.grni_account()
            grouped[grni_account.id] = Decimal(invoice.subtotal or 0)
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

        journal = JournalEntry(
            journal_number=next_document_number(self.db, "JV", digits=4),
            posting_date=invoice.invoice_date,
            status="DRAFT",
            document_type="SUPPLIER_INVOICE",
            document_number=invoice.internal_invoice_number,
            reference_type="SUPPLIER_INVOICE",
            reference_id=invoice.id,
            description=f"Supplier invoice {invoice.supplier_invoice_number}",
            created_by_id=user.id,
            business_unit_id=invoice.business_unit_id,
            location_id=invoice.location_id,
            department_id=invoice.department_id,
        )

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
            "JOURNAL_GENERATED",
            "JOURNAL_ENTRY",
            f"Generated {journal.journal_number}",
            entity_id=journal.id,
            reference_document=invoice.internal_invoice_number,
        )
        if commit:
            self.db.commit()
            self.db.refresh(journal)
        else:
            self.db.flush()
        return journal
