from datetime import date, datetime, timedelta, timezone

from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import case, func, or_
from sqlalchemy.orm import aliased
from sqlalchemy.orm import Session

from app.models.account_receivable import AccountReceivable
from app.models.accounting_setting import AccountingSetting
from app.models.accounting_posting_rule import AccountingPostingRule
from app.models.chart_of_account import ChartOfAccount
from app.models.inventory import Inventory
from app.models.warehouse import Warehouse
from app.models.stock_movement import StockMovement
from app.models.goods_receipt import GoodsReceipt, GoodsReceiptItem
from app.models.product import Product
from app.models.payment import Payment, PaymentAllocation
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.supplier_invoice import SupplierInvoice, SupplierInvoiceLine
from app.services.opening_snapshot import opening_snapshot

ZERO = Decimal("0.00")
CENT = Decimal("0.01")
OPENING_JOURNAL_TYPES = ("OPENING_BALANCE", "OPENING_BALANCE_ADJUSTMENT")


def _operational_journal():
    return or_(JournalEntry.reference_type.is_(None),
               JournalEntry.reference_type.notin_(OPENING_JOURNAL_TYPES))


def _status_for(difference: Decimal, configured: bool) -> str:
    if not configured:
        return "NOT_CONFIGURED"
    return "RECONCILED" if difference == ZERO else "OUT_OF_BALANCE"


def _visual_for(status: str, difference: Decimal | None = None) -> str:
    if status == "RECONCILED":
        return "GREEN"
    if status == "NOT_CONFIGURED":
        return "AMBER"
    if difference is not None and difference == ZERO:
        return "GREEN"
    return "RED"


class FinancialReconciliationService:
    """Read-only controls comparing current subledger balances with posted GL balances.

    Produces a closing-checklist shaped report (external statement vs GL book vs
    variance + visual indicator). Inventory is reconciled per inventory posting
    account (the accounts the goods-receipt engine actually debits), sourced from
    the stock ledger (stock_movements), with the running average-cost snapshot
    surfaced as a separate valuation check so valuation drift is visible but never
    mistaken for a posting gap.
    """

    def __init__(self, db: Session, business_unit_id: int | None = None):
        self.db = db
        self.business_unit_id = business_unit_id

    def _unit_scope(self, query, model):
        if self.business_unit_id is None:
            return query
        from sqlalchemy import select
        from app.models.location import Location
        from app.services.organization_access import effective_business_unit
        if model is JournalLine:
            location = func.coalesce(model.location_id, JournalEntry.location_id)
            unit = func.coalesce(model.business_unit_id, JournalEntry.business_unit_id)
            return query.filter(effective_business_unit(unit, location) == self.business_unit_id)
        unit = getattr(model, "business_unit_id", None)
        if unit is not None:
            return query.filter(effective_business_unit(unit, model.location_id) == self.business_unit_id)
        return query.filter(model.location_id.in_(select(Location.id).where(Location.business_unit_id == self.business_unit_id)))

    def _gl_balance(self, account_ids: list[int], location_id: int | None = None, as_of: date | None = None) -> Decimal:
        return sum(self._gl_by_account(account_ids, location_id, as_of).values(), ZERO)

    def _gl_by_account(self, account_ids: list[int], location_id: int | None = None, as_of: date | None = None) -> dict[int, Decimal]:
        """Per-account signed balance from POSTED journal lines."""
        if not account_ids:
            return {}
        snapshot_date, snapshot = opening_snapshot(
            self.db, as_of=as_of or date.today(), location_id=location_id, business_unit_id=self.business_unit_id,
        )
        query = (
            self.db.query(
                ChartOfAccount.id,
                ChartOfAccount.normal_balance,
                func.coalesce(func.sum(JournalLine.debit), 0),
                func.coalesce(func.sum(JournalLine.credit), 0),
            )
            .join(JournalLine, JournalLine.account_id == ChartOfAccount.id)
            .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
            .filter(
                ChartOfAccount.id.in_(account_ids),
                JournalEntry.status == "POSTED",
                _operational_journal(),
            )
            .group_by(ChartOfAccount.id, ChartOfAccount.normal_balance)
        )
        if snapshot_date is not None:
            query = query.filter(JournalEntry.posting_date >= snapshot_date)
        query = self._unit_scope(query, JournalLine)
        if location_id is not None:
            query = query.filter(JournalLine.location_id == location_id)
        if as_of is not None:
            query = query.filter(JournalEntry.posting_date <= as_of)
        result = {}
        for account_id, normal_balance, debit, credit in query.all():
            debit = Decimal(debit or 0)
            credit = Decimal(credit or 0)
            result[account_id] = credit - debit if normal_balance == "CREDIT" else debit - credit
        for account_id, (debit, credit) in snapshot.items():
            if account_id not in account_ids:
                continue
            account = self.db.get(ChartOfAccount, account_id)
            if account:
                signed = credit - debit if account.normal_balance == "CREDIT" else debit - credit
                result[account_id] = result.get(account_id, ZERO) + signed
        return result

    @staticmethod
    def _movement_date():
        return func.date(case(
            ((StockMovement.reference_type == "GOODS_RECEIPT")
             & (StockMovement.goods_receipt_id.is_not(None)), GoodsReceipt.received_at),
            else_=StockMovement.created_at,
        ))

    def _stock_ledger(self, account_ids: list[int] | None, location_id: int | None = None,
                      as_of: date | None = None) -> dict[int, Decimal]:
        """Signed movement values, retained as a diagnostic beside stock valuation."""
        signed = case(
            (StockMovement.movement_type == "OUT", -func.abs(StockMovement.quantity)),
            else_=func.abs(StockMovement.quantity),
        ) * StockMovement.unit_cost
        query = (
            self.db.query(StockMovement.inventory_account_id, func.coalesce(func.sum(signed), 0))
            .outerjoin(GoodsReceipt, GoodsReceipt.id == StockMovement.goods_receipt_id)
            .filter(StockMovement.inventory_account_id.is_not(None))
            .group_by(StockMovement.inventory_account_id)
        )
        if account_ids:
            query = query.filter(StockMovement.inventory_account_id.in_(account_ids))
        if location_id is not None or self.business_unit_id is not None:
            query = query.join(Warehouse, Warehouse.id == StockMovement.warehouse_id)
            query = self._unit_scope(query, Warehouse)
            if location_id is not None:
                query = query.filter(Warehouse.location_id == location_id)
        if as_of is not None:
            query = query.filter(self._movement_date() <= as_of)
        return {account_id: Decimal(value) for account_id, value in query.all()}

    def _inventory_valuation(self, location_id: int | None = None,
                             as_of: date | None = None) -> dict[int, Decimal]:
        """Current stock snapshot rolled back by subsequent signed movements."""
        query = (self.db.query(Inventory, Product)
                 .join(Product, Product.id == Inventory.product_id)
                 .join(Warehouse, Warehouse.id == Inventory.warehouse_id))
        query = self._unit_scope(query, Warehouse)
        if location_id is not None:
            query = query.filter(Warehouse.location_id == location_id)
        later = {}
        if as_of is not None:
            signed_qty = case(
                (StockMovement.movement_type == "OUT", -func.abs(StockMovement.quantity)),
                else_=func.abs(StockMovement.quantity),
            )
            movements = (self.db.query(
                StockMovement.product_id, StockMovement.warehouse_id,
                func.coalesce(func.sum(signed_qty), 0),
                func.coalesce(func.sum(signed_qty * StockMovement.unit_cost), 0),
            ).outerjoin(GoodsReceipt, GoodsReceipt.id == StockMovement.goods_receipt_id)
             .filter(self._movement_date() > as_of))
            if location_id is not None or self.business_unit_id is not None:
                movements = movements.join(Warehouse, Warehouse.id == StockMovement.warehouse_id)
                movements = self._unit_scope(movements, Warehouse)
                if location_id is not None:
                    movements = movements.filter(Warehouse.location_id == location_id)
            later = {(pid, wid): (Decimal(qty), Decimal(value))
                     for pid, wid, qty, value in movements.group_by(
                         StockMovement.product_id, StockMovement.warehouse_id
                     ).all()}
        result = {}
        for item, product in query.all():
            if product.inventory_account_id is None:
                continue
            later_qty, later_value = later.get(
                (item.product_id, item.warehouse_id), (ZERO, ZERO)
            )
            value = (Decimal(item.quantity or 0) * Decimal(item.average_cost or 0)
                     - later_value)
            result[product.inventory_account_id] = (
                result.get(product.inventory_account_id, ZERO) + value
            )
        return {key: value.quantize(Decimal("0.01")) for key, value in result.items()}

    def _unmapped_inventory_value(self, location_id: int | None = None,
                                  as_of: date | None = None) -> Decimal:
        """Value only products lacking a stock COA; rounding is never an unmapped item."""
        query = (self.db.query(Inventory)
                 .join(Product, Product.id == Inventory.product_id)
                 .join(Warehouse, Warehouse.id == Inventory.warehouse_id)
                 .filter(Product.inventory_account_id.is_(None)))
        query = self._unit_scope(query, Warehouse)
        if location_id is not None:
            query = query.filter(Warehouse.location_id == location_id)
        value = sum((Decimal(item.quantity or 0) * Decimal(item.average_cost or 0)
                     for item in query.all()), ZERO)
        if as_of is not None:
            signed = case((StockMovement.movement_type == "OUT", -func.abs(StockMovement.quantity)),
                          else_=func.abs(StockMovement.quantity)) * StockMovement.unit_cost
            later = (self.db.query(func.coalesce(func.sum(signed), 0))
                     .join(Product, Product.id == StockMovement.product_id)
                     .outerjoin(GoodsReceipt, GoodsReceipt.id == StockMovement.goods_receipt_id)
                     .filter(Product.inventory_account_id.is_(None),
                             self._movement_date() > as_of))
            if location_id is not None or self.business_unit_id is not None:
                later = later.join(Warehouse, Warehouse.id == StockMovement.warehouse_id)
                later = self._unit_scope(later, Warehouse)
                if location_id is not None:
                    later = later.filter(Warehouse.location_id == location_id)
            value -= Decimal(later.scalar() or 0)
        return value.quantize(CENT)

    def _accounts(self, account_ids: list[int]) -> list[dict]:
        if not account_ids:
            return []
        rows = (
            self.db.query(ChartOfAccount)
            .filter(ChartOfAccount.id.in_(account_ids))
            .order_by(ChartOfAccount.account_number)
            .all()
        )
        return [
            {
                "account_id": row.id,
                "account_code": row.account_number,
                "account_name": row.account_name,
                "normal_balance": row.normal_balance,
            }
            for row in rows
        ]

    def _accounts_by_id(self, account_ids: list[int]) -> dict[int, dict]:
        return {row["account_id"]: row for row in self._accounts(account_ids)}

    def _rule_account_ids(self, *, debit: bool, event_types: list[str], location_id: int | None = None) -> list[int]:
        column = (
            AccountingPostingRule.debit_account_id
            if debit
            else AccountingPostingRule.credit_account_id
        )
        query = (
            self.db.query(column)
            .filter(
                AccountingPostingRule.is_active.is_(True),
                AccountingPostingRule.event_type.in_(event_types),
            )
        )
        if location_id is not None:
            query = query.filter(
                (AccountingPostingRule.location_id == location_id)
                | (AccountingPostingRule.location_id.is_(None))
            )
        rows = query.distinct().all()
        return sorted({int(value) for (value,) in rows if value is not None})

    @staticmethod
    def _detail_row(
        control: str,
        source: Decimal,
        gl: Decimal,
        *,
        account: dict | None = None,
        configured: bool = True,
    ) -> dict:
        difference = source - gl
        status = _status_for(difference, configured)
        return {
            "control": control,
            "account_id": account["account_id"] if account else None,
            "account_code": account["account_code"] if account else None,
            "account_name": account["account_name"] if account else None,
            "external_statement": source,
            "source_balance": source,
            "gl_balance": gl,
            "variance": difference,
            "status": status,
            "visual": _visual_for(status, difference),
        }

    @staticmethod
    def _row(
        control: str,
        source: Decimal,
        gl: Decimal,
        accounts: list[dict],
        configured: bool = True,
        detail: list[dict] | None = None,
        variance_breakdown: dict[str, Decimal] | None = None,
    ) -> dict:
        difference = source - gl
        status = _status_for(difference, configured)
        row = {
            "control": control,
            "external_statement": source,
            "source_balance": source,
            "gl_balance": gl,
            "variance": difference,
            "difference": difference,
            "status": status,
            "visual": _visual_for(status, difference),
            "configured": configured,
            "accounts": accounts,
            "variance_breakdown": variance_breakdown or {},
        }
        if detail is not None:
            row["detail"] = detail
        return row

    def _unallocated_payments(self, location_id: int | None, as_of: date | None):
        """Posted payments whose invoice allocations do not cover their amount."""
        allocated = (self.db.query(
            PaymentAllocation.payment_id,
            func.coalesce(func.sum(PaymentAllocation.allocated_amount), 0).label("amount"),
        ).join(SupplierInvoice, SupplierInvoice.id == PaymentAllocation.supplier_invoice_id)
         .filter(SupplierInvoice.status == "POSTED")
         .group_by(PaymentAllocation.payment_id).subquery())
        query = (self.db.query(Payment, allocated.c.amount)
                 .outerjoin(allocated, allocated.c.payment_id == Payment.id)
                 .filter(Payment.status == "POSTED"))
        query = self._unit_scope(query, Payment)
        if location_id is not None:
            query = query.filter(Payment.location_id == location_id)
        if as_of is not None:
            query = query.filter(Payment.payment_date <= as_of)
        result = []
        for payment, amount in query.order_by(Payment.payment_date, Payment.id).all():
            unallocated = Decimal(payment.amount or 0) - Decimal(amount or 0)
            if unallocated > ZERO:
                result.append({
                    "kind": "UNALLOCATED_PAYMENT", "document_id": payment.id,
                    "document_number": payment.payment_number,
                    "date": payment.payment_date, "supplier_id": payment.supplier_id,
                    "amount": unallocated,
                })
        return result

    def _suspense_journals(self, account_ids: list[int], location_id: int | None,
                           as_of: date | None):
        if not account_ids:
            return []
        query = (self.db.query(JournalEntry, JournalLine)
                 .join(JournalLine, JournalLine.journal_entry_id == JournalEntry.id)
                 .filter(JournalEntry.status == "POSTED", JournalLine.account_id.in_(account_ids)))
        query = self._unit_scope(query, JournalLine)
        if location_id is not None:
            query = query.filter(JournalLine.location_id == location_id)
        if as_of is not None:
            query = query.filter(JournalEntry.posting_date <= as_of)
        return [{
            "kind": "SUSPENSE_JOURNAL", "document_id": journal.id,
            "document_number": journal.document_number or journal.journal_number,
            "date": journal.posting_date, "supplier_id": line.supplier_id,
            "reference_type": journal.reference_type, "reference_id": journal.reference_id,
            "debit": line.debit, "credit": line.credit,
            "amount": Decimal(line.credit or 0) - Decimal(line.debit or 0),
        } for journal, line in query.order_by(
            JournalEntry.posting_date.desc(), JournalLine.id.desc()
        ).limit(100).all()]

    def _ap_documents(self, account_ids: list[int], location_id: int | None,
                      as_of: date | None, closing_source: Decimal) -> tuple[list[dict], dict]:
        """Bridge posted invoices and allocated payments to AP journal lines.

        Opening AP has no supplier subledger in this installation, so its
        journal impact is displayed separately instead of inventing invoices.
        """
        if not account_ids:
            return [], {}
        invoices = self.db.query(SupplierInvoice).filter(SupplierInvoice.status == "POSTED")
        invoices = self._unit_scope(invoices, SupplierInvoice)
        if location_id is not None:
            invoices = invoices.filter(SupplierInvoice.location_id == location_id)
        if as_of is not None:
            invoices = invoices.filter(SupplierInvoice.invoice_date <= as_of)
        invoice_rows = invoices.order_by(SupplierInvoice.invoice_date, SupplierInvoice.id).all()
        invoice_ids = [invoice.id for invoice in invoice_rows]

        allocated_by_payment: dict[int, Decimal] = {}
        if invoice_ids:
            allocations = (self.db.query(PaymentAllocation, Payment)
                           .join(Payment, Payment.id == PaymentAllocation.payment_id)
                           .filter(PaymentAllocation.supplier_invoice_id.in_(invoice_ids),
                                   Payment.status == "POSTED"))
            if as_of is not None:
                allocations = allocations.filter(Payment.payment_date <= as_of)
            for allocation, payment in allocations.all():
                allocated_by_payment[payment.id] = (
                    allocated_by_payment.get(payment.id, ZERO)
                    + Decimal(allocation.allocated_amount or 0)
                )

        payments = self.db.query(Payment).filter(Payment.status == "POSTED")
        payments = self._unit_scope(payments, Payment)
        if location_id is not None:
            payments = payments.filter(Payment.location_id == location_id)
        if as_of is not None:
            payments = payments.filter(Payment.payment_date <= as_of)
        payment_by_id = {payment.id: payment for payment in payments.all()}
        # Cross-location allocations still affect the invoice source. Show
        # the payment even when its own location differs from this GL scope.
        if allocated_by_payment:
            for payment in self.db.query(Payment).filter(
                    Payment.id.in_(allocated_by_payment)).all():
                payment_by_id.setdefault(payment.id, payment)

        snapshot_date, snapshot = opening_snapshot(
            self.db, as_of=as_of or date.today(), location_id=location_id, business_unit_id=self.business_unit_id,
        )
        normals = {row.id: row.normal_balance for row in self.db.query(ChartOfAccount)
                   .filter(ChartOfAccount.id.in_(account_ids)).all()}
        journal_query = (self.db.query(JournalEntry, JournalLine)
                         .join(JournalLine, JournalLine.journal_entry_id == JournalEntry.id)
                         .filter(JournalEntry.status == "POSTED",
                                 JournalLine.account_id.in_(account_ids),
                                 _operational_journal()))
        if snapshot_date is not None:
            journal_query = journal_query.filter(JournalEntry.posting_date >= snapshot_date)
        if as_of is not None:
            journal_query = journal_query.filter(JournalEntry.posting_date <= as_of)
        journal_query = self._unit_scope(journal_query, JournalLine)
        if location_id is not None:
            journal_query = journal_query.filter(JournalLine.location_id == location_id)
        by_journal: dict[int, dict] = {}
        for journal, line in journal_query.all():
            signed = (Decimal(line.credit or 0) - Decimal(line.debit or 0)
                      if normals[line.account_id] == "CREDIT"
                      else Decimal(line.debit or 0) - Decimal(line.credit or 0))
            if journal.id not in by_journal:
                by_journal[journal.id] = {"journal": journal, "gl": ZERO}
            by_journal[journal.id]["gl"] += signed

        used_journals: set[int] = set()
        documents: list[dict] = []

        def linked(reference_types: tuple[str, ...], document_id: int) -> tuple[Decimal, list[int]]:
            matches = [item for item in by_journal.values()
                       if item["journal"].reference_type in reference_types
                       and item["journal"].reference_id == document_id]
            ids = [item["journal"].id for item in matches]
            used_journals.update(ids)
            return sum((item["gl"] for item in matches), ZERO), ids

        source_activity = ZERO
        for invoice in invoice_rows:
            source_amount = Decimal(invoice.total_amount or 0) - Decimal(invoice.adjustment_amount or 0)
            source_activity += source_amount
            gl_amount, journal_ids = linked(("SUPPLIER_INVOICE",), invoice.id)
            documents.append({
                "kind": "INVOICE", "document_id": invoice.id,
                "document_number": invoice.internal_invoice_number,
                "date": invoice.invoice_date, "supplier_id": invoice.supplier_id,
                "source_amount": source_amount, "gl_amount": gl_amount,
                "difference": source_amount - gl_amount,
                "journal_ids": journal_ids,
            })

        for payment in payment_by_id.values():
            source_amount = -allocated_by_payment.get(payment.id, ZERO)
            source_activity += source_amount
            gl_amount, journal_ids = linked(("SUPPLIER_PAYMENT", "PAYMENT"), payment.id)
            documents.append({
                "kind": "PAYMENT", "document_id": payment.id,
                "document_number": payment.payment_number,
                "date": payment.payment_date, "supplier_id": payment.supplier_id,
                "source_amount": source_amount, "gl_amount": gl_amount,
                "difference": source_amount - gl_amount,
                "journal_ids": journal_ids,
            })

        for journal_id, item in by_journal.items():
            if journal_id in used_journals:
                continue
            journal = item["journal"]
            documents.append({
                "kind": "GL_ONLY_JOURNAL", "document_id": journal_id,
                "document_number": journal.document_number or journal.journal_number,
                "date": journal.posting_date, "supplier_id": None,
                "source_amount": ZERO, "gl_amount": item["gl"],
                "difference": -item["gl"], "journal_ids": [journal_id],
                "reference_type": journal.reference_type,
            })

        drift = closing_source - source_activity
        if drift != ZERO:
            documents.append({
                "kind": "SOURCE_BALANCE_DRIFT", "document_id": None,
                "document_number": "Invoice balance fields", "date": None,
                "supplier_id": None, "source_amount": drift,
                "gl_amount": ZERO, "difference": drift, "journal_ids": [],
            })

        opening_gl = ZERO
        for account_id, (debit, credit) in snapshot.items():
            if account_id in normals:
                opening_gl += (credit - debit if normals[account_id] == "CREDIT"
                               else debit - credit)
        if opening_gl != ZERO:
            documents.append({
                "kind": "OPENING_GL", "document_id": None,
                "document_number": f"Opening {snapshot_date.year}",
                "date": snapshot_date, "supplier_id": None,
                "source_amount": None, "gl_amount": opening_gl,
                "difference": -opening_gl, "journal_ids": [],
            })
        documents.sort(key=lambda item: (abs(item["difference"]),
                                         item["date"] or date.min), reverse=True)
        return documents, {
            "source_activity": source_activity,
            "source_balance_drift": drift,
            "opening_gl": opening_gl,
            "document_difference_total": sum((item["difference"] for item in documents), ZERO),
        }

    def accounts_payable(self, location_id: int | None = None,
                         as_of: date | None = None) -> dict:
        source_query = self.db.query(func.coalesce(func.sum(SupplierInvoice.balance_amount), 0)).filter(
            SupplierInvoice.status == "POSTED"
        )
        source_query = self._unit_scope(source_query, SupplierInvoice)
        if location_id is not None:
            source_query = source_query.filter(SupplierInvoice.location_id == location_id)
        if as_of is None:
            source = Decimal(source_query.scalar() or 0)
        else:
            # Rebuild the dated balance from invoice amounts and posted allocations.
            invoices = self.db.query(SupplierInvoice).filter(
                SupplierInvoice.status == "POSTED", SupplierInvoice.invoice_date <= as_of
            )
            invoices = self._unit_scope(invoices, SupplierInvoice)
            if location_id is not None:
                invoices = invoices.filter(SupplierInvoice.location_id == location_id)
            invoice_rows = invoices.all()
            ids = [item.id for item in invoice_rows]
            allocations = ZERO
            if ids:
                allocations = Decimal((self.db.query(
                    func.coalesce(func.sum(PaymentAllocation.allocated_amount), 0)
                ).join(Payment, Payment.id == PaymentAllocation.payment_id)
                 .filter(PaymentAllocation.supplier_invoice_id.in_(ids),
                         Payment.status == "POSTED", Payment.payment_date <= as_of)
                 .scalar()) or 0)
            source = sum((Decimal(item.total_amount or 0) -
                          Decimal(item.adjustment_amount or 0) for item in invoice_rows), ZERO) - allocations
        account_ids = self._rule_account_ids(
            debit=False,
            event_types=["SUPPLIER_INVOICE_INVENTORY", "SUPPLIER_INVOICE_DIRECT_USE"],
            location_id=location_id,
        )
        gl = self._gl_balance(account_ids, location_id, as_of)
        row = self._row("ACCOUNTS_PAYABLE", source, gl, self._accounts(account_ids),
                        configured=bool(account_ids),
                        variance_breakdown={"posting_mismatch": source - gl})
        row["ap_documents"], row["ap_document_summary"] = self._ap_documents(
            account_ids, location_id, as_of, source,
        )
        row["exceptions"] = self._unallocated_payments(location_id, as_of)
        if row["ap_document_summary"].get("opening_gl"):
            row["note"] = ("GL includes a manual opening AP balance. Supplier-level opening "
                           "payables are unavailable; review opening separately from 2026 activity.")
        if as_of is not None:
            row["note"] = (row.get("note", "") + " Dated AP uses invoice totals and posted "
                           "allocations; invoice adjustments have no historical effective date.").strip()
        return row

    def accounts_receivable(self, location_id: int | None = None,
                            as_of: date | None = None) -> dict:
        if location_id is not None or self.business_unit_id is not None:
            row = self._row("ACCOUNTS_RECEIVABLE", ZERO, ZERO, [], configured=False)
            row.update(source_balance=None, difference=None, variance=None, note="AR source records have no unit or location dimension.")
            return row
        account_ids = self._rule_account_ids(
            debit=False, event_types=["CUSTOMER_PAYMENT"],
        )
        gl = self._gl_balance(account_ids, location_id, as_of)
        if as_of is not None and as_of < datetime.now(timezone.utc).date():
            row = self._row("ACCOUNTS_RECEIVABLE", ZERO, gl,
                            self._accounts(account_ids), configured=False)
            row.update(status="HISTORY_UNAVAILABLE", source_balance=None,
                       external_statement=None, variance=None, difference=None,
                       visual="AMBER",
                       note="AR has no dated payment ledger; historical source balance cannot be reconstructed.")
            return row
        source = Decimal(
            self.db.query(func.coalesce(func.sum(AccountReceivable.outstanding_amount), 0)).scalar()
            or 0
        )
        return self._row(
            "ACCOUNTS_RECEIVABLE", source, gl, self._accounts(account_ids),
            configured=bool(account_ids),
            variance_breakdown={"posting_mismatch": source - gl},
        )

    def clearing_suspense(self, location_id: int | None = None,
                          as_of: date | None = None) -> dict:
        setting = (self.db.query(AccountingSetting)
                   .filter(AccountingSetting.setting_key == "AP_SUSPENSE_ACCOUNT").first())
        account = self.db.get(ChartOfAccount, setting.account_id) if setting else None
        if not account or not account.is_active:
            row = self._row("CLEARING_SUSPENSE", ZERO, ZERO, [], configured=False)
            row["note"] = "Map an active AP Suspense account before reconciling receipts."
            return row

        receipts = (self.db.query(GoodsReceipt)
                    .filter(GoodsReceipt.status == "POSTED",
                            func.date(GoodsReceipt.received_at) >= date(2026, 1, 1)))
        if as_of is not None:
            receipts = receipts.filter(func.date(GoodsReceipt.received_at) <= as_of)
        receipts = self._unit_scope(receipts, GoodsReceipt)
        if location_id is not None:
            receipts = receipts.filter(GoodsReceipt.location_id == location_id)
        receipt_rows = receipts.order_by(GoodsReceipt.received_at, GoodsReceipt.id).all()
        receipt_by_id = {receipt.id: receipt for receipt in receipt_rows}
        receipt_ids = [receipt.id for receipt in receipt_rows]
        received = {}
        invoiced = {}
        invoice_net = {}
        item_rows = {}
        invoiced_quantity = {}
        match_issues = []
        invoice_numbers: dict[int, set[str]] = {}
        posted_documents: dict[int, dict[int, dict]] = {}
        pending_documents: dict[int, dict[int, dict]] = {}
        if receipt_ids:
            for item in (self.db.query(GoodsReceiptItem)
                         .filter(GoodsReceiptItem.goods_receipt_id.in_(receipt_ids)).all()):
                item_rows[item.id] = item
                receipt_cost = (Decimal(item.quantity or 0)
                                * Decimal(item.unit_cost or 0)).quantize(CENT, rounding=ROUND_HALF_UP)
                received[item.goods_receipt_id] = (
                    received.get(item.goods_receipt_id, ZERO) + receipt_cost
                )
            invoice_lines = (self.db.query(SupplierInvoiceLine, SupplierInvoice,
                                           GoodsReceiptItem.goods_receipt_id)
                             .join(SupplierInvoice, SupplierInvoice.id == SupplierInvoiceLine.supplier_invoice_id)
                             .join(GoodsReceiptItem, GoodsReceiptItem.id == SupplierInvoiceLine.goods_receipt_item_id)
                             .filter(SupplierInvoice.status.in_(("POSTED", "DRAFT", "VERIFIED")),
                                     GoodsReceiptItem.goods_receipt_id.in_(receipt_ids)))
            if as_of is not None:
                invoice_lines = invoice_lines.filter(SupplierInvoice.invoice_date <= as_of)
            invoice_lines = self._unit_scope(invoice_lines, SupplierInvoice)
            if location_id is not None:
                invoice_lines = invoice_lines.filter(SupplierInvoice.location_id == location_id)
            for line, invoice, receipt_id in invoice_lines.all():
                document = {
                    "invoice_id": invoice.id,
                    "invoice_number": invoice.internal_invoice_number,
                    "status": invoice.status,
                }
                if invoice.status != "POSTED":
                    pending_documents.setdefault(receipt_id, {})[invoice.id] = document
                    continue
                posted_documents.setdefault(receipt_id, {})[invoice.id] = document
                receipt = receipt_by_id[receipt_id]
                item = item_rows[line.goods_receipt_item_id]
                if (receipt.supplier_id is not None
                        and invoice.supplier_id != receipt.supplier_id):
                    match_issues.append({
                        "receipt_id": receipt_id, "receipt_item_id": item.id,
                        "invoice_id": invoice.id, "issue": "SUPPLIER_MISMATCH",
                    })
                    continue
                if (receipt.location_id is not None and invoice.location_id is not None
                        and invoice.location_id != receipt.location_id):
                    match_issues.append({
                        "receipt_id": receipt_id, "receipt_item_id": item.id,
                        "invoice_id": invoice.id, "issue": "LOCATION_MISMATCH",
                    })
                    continue
                if line.product_id is not None and line.product_id != item.product_id:
                    match_issues.append({
                        "receipt_id": receipt_id, "receipt_item_id": item.id,
                        "invoice_id": invoice.id, "issue": "PRODUCT_MISMATCH",
                    })
                    continue
                invoiced_quantity[line.goods_receipt_item_id] = (
                    invoiced_quantity.get(line.goods_receipt_item_id, ZERO)
                    + Decimal(line.quantity or 0)
                )
                invoice_net[receipt_id] = (
                    invoice_net.get(receipt_id, ZERO)
                    + Decimal(line.line_amount or 0)
                )
                invoice_numbers.setdefault(receipt_id, set()).add(invoice.internal_invoice_number)

        open_items: dict[int, list[dict]] = {}
        for item in item_rows.values():
            quantity = Decimal(item.quantity or 0)
            billed_quantity = invoiced_quantity.get(item.id, ZERO)
            if billed_quantity > quantity:
                match_issues.append({
                    "receipt_id": item.goods_receipt_id,
                    "receipt_item_id": item.id,
                    "issue": "INVOICED_QUANTITY_EXCEEDS_RECEIVED",
                    "received_quantity": quantity,
                    "invoiced_quantity": billed_quantity,
                })
            # A fully invoiced receipt item must clear exactly the amount
            # originally accrued, including any cent rounding at receipt.
            received_value = (quantity * Decimal(item.unit_cost or 0)).quantize(CENT, rounding=ROUND_HALF_UP)
            open_quantity = quantity - billed_quantity
            open_value = (open_quantity * Decimal(item.unit_cost or 0)).quantize(CENT, rounding=ROUND_HALF_UP)
            if open_quantity != ZERO:
                open_items.setdefault(item.goods_receipt_id, []).append({
                    "receipt_item_id": item.id, "product_id": item.product_id,
                    "received_quantity": quantity, "invoiced_quantity": billed_quantity,
                    "outstanding_quantity": open_quantity,
                    "receipt_unit_cost": Decimal(item.unit_cost or 0),
                    "outstanding_amount": open_value,
                })
            invoiced[item.goods_receipt_id] = (
                invoiced.get(item.goods_receipt_id, ZERO) + received_value - open_value
            )

        evidence = []
        price_evidence = []
        source = ZERO
        for receipt in receipt_rows:
            gross = received.get(receipt.id, ZERO)
            cleared = invoiced.get(receipt.id, ZERO)
            invoice_amount = invoice_net.get(receipt.id, ZERO).quantize(CENT)
            outstanding = gross - cleared
            source += outstanding
            if invoice_amount != cleared:
                price_evidence.append({
                    "receipt_id": receipt.id, "receipt_number": receipt.receipt_number,
                    "invoice_numbers": sorted(invoice_numbers.get(receipt.id, set())),
                    "cleared_receipt_cost": cleared, "invoice_net_amount": invoice_amount,
                    "price_difference": invoice_amount - cleared,
                })
            if outstanding != ZERO:
                evidence.append({
                    "receipt_id": receipt.id, "receipt_number": receipt.receipt_number,
                    "date": receipt.received_at.date(), "supplier_id": receipt.supplier_id,
                    "supplier_name": receipt.supplier.name if receipt.supplier else None,
                    "received_amount": gross, "invoiced_amount": cleared,
                    "outstanding_amount": outstanding,
                    "invoice_net_amount": invoice_amount,
                    "invoice_numbers": sorted(invoice_numbers.get(receipt.id, set())),
                    "posted_invoices": sorted(posted_documents.get(receipt.id, {}).values(), key=lambda doc: doc["invoice_number"]),
                    "pending_invoices": sorted(pending_documents.get(receipt.id, {}).values(), key=lambda doc: doc["invoice_number"]),
                    "items": open_items.get(receipt.id, []),
                })

        gl = self._gl_balance([account.id], location_id, as_of)
        accounts = self._accounts([account.id])
        row = self._row(
            "CLEARING_SUSPENSE", source, gl, accounts,
            detail=[self._detail_row(f"CLR_{accounts[0]['account_code']}",
                                     source, gl, account=accounts[0])],
            variance_breakdown={"receipt_accrual_difference": source - gl},
        )
        if row["status"] == "RECONCILED" and source != ZERO:
            row.update(status="OPEN_ITEMS", visual="AMBER")
        if match_issues:
            row.update(status="OUT_OF_BALANCE", visual="RED")
        row["receipt_evidence"] = evidence
        row["price_variance_evidence"] = price_evidence
        row["match_issues"] = match_issues
        row["exceptions"] = self._suspense_journals([account.id], location_id, as_of)
        if source != ZERO:
            row["note"] = ("Open receipt accrual is expected until matching invoices clear it. "
                           "Compare each receipt with the posted AP Suspense balance.")
        return row

    def inventory(self, location_id: int | None = None,
                  as_of: date | None = None) -> dict:
        rule_ids = self._rule_account_ids(
            debit=True, event_types=["SUPPLIER_INVOICE_INVENTORY"],
            location_id=location_id,
        )
        product_accounts = (self.db.query(Product.inventory_account_id)
                            .filter(Product.inventory_account_id.is_not(None)))
        if location_id is not None:
            product_accounts = (product_accounts.join(
                Inventory, Inventory.product_id == Product.id
            ).join(Warehouse, Warehouse.id == Inventory.warehouse_id)
             .filter(Warehouse.location_id == location_id))
        product_ids = {account_id for (account_id,) in product_accounts.distinct().all()}
        ledger_by = self._stock_ledger(None, location_id, as_of)
        valuation_by = self._inventory_valuation(location_id, as_of)
        # The hotel's inventory chart includes accounts with opening GL balances
        # even when no current product or movement points to them.
        chart_inventory_ids = {
            account_id for (account_id,) in self.db.query(ChartOfAccount.id).filter(
                ChartOfAccount.account_type == "ASSET",
                ChartOfAccount.account_number.like("100-300-%"),
            ).all()
        }
        account_ids = sorted(set(rule_ids) | product_ids | chart_inventory_ids |
                             set(ledger_by) | set(valuation_by))
        gl_by = self._gl_by_account(account_ids, location_id, as_of)
        source = sum(valuation_by.values(), ZERO)
        gl = sum(gl_by.values(), ZERO)
        # Inspect missing mappings directly. Sub-cent weighted-average rounding
        # must not be treated as stock without a COA.
        unmapped_stock = self._unmapped_inventory_value(location_id, as_of)
        account_meta = self._accounts_by_id(account_ids)
        detail = []
        for account_id in sorted(account_ids, key=lambda aid: (
            account_meta.get(aid, {}).get("account_code") or "", aid
        )):
            acc = account_meta.get(account_id)
            if acc is None:
                continue
            row = self._detail_row(
                f"INV_{acc['account_code']}",
                valuation_by.get(account_id, ZERO), gl_by.get(account_id, ZERO),
                account=acc,
            )
            row["movement_value"] = ledger_by.get(account_id, ZERO)
            detail.append(row)
        row = self._row(
            "INVENTORY", source, gl, self._accounts(account_ids),
            configured=bool(account_ids), detail=detail,
            variance_breakdown={"posting_mismatch": source - gl,
                                "valuation_method": (source + unmapped_stock -
                                                     sum(ledger_by.values(), ZERO)).quantize(CENT),
                                "unmapped_stock": unmapped_stock},
        )
        if unmapped_stock != ZERO and row["status"] == "RECONCILED":
            row["status"] = "OUT_OF_BALANCE"
            row["visual"] = "RED"
        if unmapped_stock != ZERO:
            row["note"] = f"Stock without an inventory account: {unmapped_stock}. Assign its product COA before closing."
        elif as_of is not None:
            row["note"] = ("Historical stock valuation is reconstructed from the current snapshot "
                           "and later movement costs; review average-cost and opening adjustments.")
        return row

    def _snapshot(self, location_id: int | None, as_of: date | None) -> list[dict]:
        return [
            self.accounts_payable(location_id, as_of),
            self.accounts_receivable(location_id, as_of),
            self.clearing_suspense(location_id, as_of),
            self.inventory(location_id, as_of),
        ]

    def _journal_counterparts(self, items: list[dict], location_id: int | None,
                              as_of: date | None) -> None:
        """Other posted lines in journals containing a controlled account.

        Pairing is journal-level evidence. Debit/credit amounts on multi-line
        journals are not attributed to any particular controlled line.
        """
        account_ids = sorted({
            account["account_id"] for row in items for account in row["accounts"]
        })
        for row in items:
            row["counterparts"] = []
        if not account_ids:
            return

        target = aliased(JournalLine)
        other = aliased(JournalLine)
        journals = (
            self.db.query(
                target.account_id.label("account_id"),
                target.journal_entry_id.label("journal_entry_id"),
            )
            .join(JournalEntry, JournalEntry.id == target.journal_entry_id)
            .filter(
                target.account_id.in_(account_ids),
                JournalEntry.status == "POSTED",
                _operational_journal(),
            )
        )
        if self.business_unit_id is not None:
            from app.services.organization_access import effective_business_unit
            journals = journals.filter(effective_business_unit(func.coalesce(target.business_unit_id, JournalEntry.business_unit_id),func.coalesce(target.location_id,JournalEntry.location_id)) == self.business_unit_id)
        if location_id is not None:
            journals = journals.filter(target.location_id == location_id)
        if as_of is not None:
            journals = journals.filter(JournalEntry.posting_date <= as_of)
        journals = journals.distinct().subquery()

        matches = (
            self.db.query(
                journals.c.account_id,
                ChartOfAccount.id, ChartOfAccount.account_number,
                ChartOfAccount.account_name,
                func.count(func.distinct(other.journal_entry_id)),
                func.coalesce(func.sum(other.debit), 0),
                func.coalesce(func.sum(other.credit), 0),
            )
            .join(other, other.journal_entry_id == journals.c.journal_entry_id)
            .join(ChartOfAccount, ChartOfAccount.id == other.account_id)
            .filter(other.account_id != journals.c.account_id)
        )
        if self.business_unit_id is not None:
            from sqlalchemy import select
            header_unit = select(JournalEntry.business_unit_id).where(JournalEntry.id == other.journal_entry_id).scalar_subquery()
            header_location = select(JournalEntry.location_id).where(JournalEntry.id == other.journal_entry_id).scalar_subquery()
            matches = matches.filter(effective_business_unit(func.coalesce(other.business_unit_id,header_unit),func.coalesce(other.location_id,header_location)) == self.business_unit_id)
        if location_id is not None:
            matches = matches.filter(other.location_id == location_id)
        matches = matches.group_by(
            journals.c.account_id, ChartOfAccount.id,
            ChartOfAccount.account_number, ChartOfAccount.account_name,
        ).order_by(journals.c.account_id, ChartOfAccount.account_number)

        by_account: dict[int, list[dict]] = {}
        for target_id, opposite_id, code, name, count, debit, credit in matches.all():
            by_account.setdefault(target_id, []).append({
                "account_id": target_id,
                "counterpart_account_id": opposite_id,
                "counterpart_code": code,
                "counterpart_name": name,
                "journal_count": int(count),
                "counterpart_debit": Decimal(debit),
                "counterpart_credit": Decimal(credit),
            })
        for row in items:
            for account in row["accounts"]:
                row["counterparts"].extend(by_account.get(account["account_id"], []))

    def report(self, location_id: int | None = None, date_from: date | None = None,
               date_to: date | None = None) -> dict:
        as_of = date_to
        items = self._snapshot(location_id, as_of)
        self._journal_counterparts(items, location_id, as_of)
        if date_from is not None:
            opening = {
                row["control"]: row for row in self._snapshot(
                    location_id, date_from - timedelta(days=1)
                )
            }
            for row in items:
                before = opening[row["control"]]
                if before["source_balance"] is None or row["source_balance"] is None:
                    row["period"] = {
                        "opening_source": None, "opening_gl": before["gl_balance"],
                        "source_change": None,
                        "gl_change": row["gl_balance"] - before["gl_balance"],
                    }
                else:
                    row["period"] = {
                        "opening_source": before["source_balance"],
                        "opening_gl": before["gl_balance"],
                        "source_change": row["source_balance"] - before["source_balance"],
                        "gl_change": row["gl_balance"] - before["gl_balance"],
                    }
        total_variance = sum(
            (row["variance"] for row in items
             if row["status"] == "OUT_OF_BALANCE"), ZERO,
        )
        result = {
            "items": items,
            "summary": {
                "reconciled": sum(row["status"] == "RECONCILED" for row in items),
                "out_of_balance": sum(row["status"] == "OUT_OF_BALANCE" for row in items),
                "open_items": sum(row["status"] == "OPEN_ITEMS" for row in items),
                "not_configured": sum(row["status"] == "NOT_CONFIGURED" for row in items),
                "history_unavailable": sum(row["status"] == "HISTORY_UNAVAILABLE" for row in items),
                "ready_to_close": all(row["status"] == "RECONCILED" for row in items),
                "variance_tracker": {
                    "total_variance": total_variance,
                    "checks": len(items),
                    "green": sum(row["visual"] == "GREEN" for row in items),
                    "amber": sum(row["visual"] == "AMBER" for row in items),
                    "red": sum(row["visual"] == "RED" for row in items),
                },
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            "scope": "DATE_RANGE" if date_from or date_to else "CURRENT_BALANCE",
            "read_only": True,
        }
        if date_from is not None or date_to is not None:
            result["date_from"] = date_from
            result["date_to"] = date_to
        return result
