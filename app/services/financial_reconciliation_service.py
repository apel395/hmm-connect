from datetime import date, datetime, timedelta, timezone

from decimal import Decimal

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.account_receivable import AccountReceivable
from app.models.accounting_posting_rule import AccountingPostingRule
from app.models.chart_of_account import ChartOfAccount
from app.models.inventory import Inventory
from app.models.warehouse import Warehouse
from app.models.stock_movement import StockMovement
from app.models.goods_receipt import GoodsReceipt
from app.models.product import Product
from app.models.payment import Payment, PaymentAllocation
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.supplier_invoice import SupplierInvoice

ZERO = Decimal("0.00")


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

    def __init__(self, db: Session):
        self.db = db

    def _gl_balance(self, account_ids: list[int], location_id: int | None = None, as_of: date | None = None) -> Decimal:
        return sum(self._gl_by_account(account_ids, location_id, as_of).values(), ZERO)

    def _gl_by_account(self, account_ids: list[int], location_id: int | None = None, as_of: date | None = None) -> dict[int, Decimal]:
        """Per-account signed balance from POSTED journal lines."""
        if not account_ids:
            return {}
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
            )
            .group_by(ChartOfAccount.id, ChartOfAccount.normal_balance)
        )
        if location_id is not None:
            query = query.filter(JournalLine.location_id == location_id)
        if as_of is not None:
            query = query.filter(JournalEntry.posting_date <= as_of)
        result = {}
        for account_id, normal_balance, debit, credit in query.all():
            debit = Decimal(debit or 0)
            credit = Decimal(credit or 0)
            result[account_id] = credit - debit if normal_balance == "CREDIT" else debit - credit
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
            (StockMovement.movement_type == "OUT", -StockMovement.quantity),
            else_=StockMovement.quantity,
        ) * StockMovement.unit_cost
        query = (
            self.db.query(StockMovement.inventory_account_id, func.coalesce(func.sum(signed), 0))
            .outerjoin(GoodsReceipt, GoodsReceipt.id == StockMovement.goods_receipt_id)
            .filter(StockMovement.inventory_account_id.is_not(None))
            .group_by(StockMovement.inventory_account_id)
        )
        if account_ids:
            query = query.filter(StockMovement.inventory_account_id.in_(account_ids))
        if location_id is not None:
            query = query.join(Warehouse, Warehouse.id == StockMovement.warehouse_id).filter(
                Warehouse.location_id == location_id
            )
        if as_of is not None:
            query = query.filter(self._movement_date() <= as_of)
        return {account_id: Decimal(value) for account_id, value in query.all()}

    def _inventory_valuation(self, location_id: int | None = None,
                             as_of: date | None = None) -> dict[int, Decimal]:
        """Current stock snapshot rolled back by subsequent signed movements."""
        query = (self.db.query(Inventory, Product)
                 .join(Product, Product.id == Inventory.product_id)
                 .join(Warehouse, Warehouse.id == Inventory.warehouse_id))
        if location_id is not None:
            query = query.filter(Warehouse.location_id == location_id)
        later = {}
        if as_of is not None:
            signed_qty = case(
                (StockMovement.movement_type == "OUT", -StockMovement.quantity),
                else_=StockMovement.quantity,
            )
            movements = (self.db.query(
                StockMovement.product_id, StockMovement.warehouse_id,
                func.coalesce(func.sum(signed_qty), 0),
                func.coalesce(func.sum(signed_qty * StockMovement.unit_cost), 0),
            ).outerjoin(GoodsReceipt, GoodsReceipt.id == StockMovement.goods_receipt_id)
             .filter(self._movement_date() > as_of))
            if location_id is not None:
                movements = movements.join(
                    Warehouse, Warehouse.id == StockMovement.warehouse_id
                ).filter(Warehouse.location_id == location_id)
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
        ).group_by(PaymentAllocation.payment_id).subquery())
        query = (self.db.query(Payment, allocated.c.amount)
                 .outerjoin(allocated, allocated.c.payment_id == Payment.id)
                 .filter(Payment.status == "POSTED"))
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

    def accounts_payable(self, location_id: int | None = None,
                         as_of: date | None = None) -> dict:
        source_query = self.db.query(func.coalesce(func.sum(SupplierInvoice.balance_amount), 0)).filter(
            SupplierInvoice.status == "POSTED"
        )
        if location_id is not None:
            source_query = source_query.filter(SupplierInvoice.location_id == location_id)
        if as_of is None:
            source = Decimal(source_query.scalar() or 0)
        else:
            # Rebuild the dated balance from invoice amounts and posted allocations.
            invoices = self.db.query(SupplierInvoice).filter(
                SupplierInvoice.status == "POSTED", SupplierInvoice.invoice_date <= as_of
            )
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
        row["exceptions"] = self._unallocated_payments(location_id, as_of)
        if as_of is not None:
            row["note"] = ("Dated AP source uses posted invoice totals and payment allocations; "
                           "undated invoice adjustments have no historical effective date.")
        return row

    def accounts_receivable(self, location_id: int | None = None,
                            as_of: date | None = None) -> dict:
        if location_id is not None:
            return self._row("ACCOUNTS_RECEIVABLE", ZERO, ZERO, [], configured=False)
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
        rows = (self.db.query(ChartOfAccount)
                .filter(ChartOfAccount.account_name.ilike("%suspense%"),
                        ChartOfAccount.is_active.is_(True))
                .order_by(ChartOfAccount.account_number).all())
        account_ids = [row.id for row in rows]
        gl_by = self._gl_by_account(account_ids, location_id, as_of)
        gl = sum(gl_by.values(), ZERO)
        accounts = self._accounts(account_ids)
        row = self._row(
            "CLEARING_SUSPENSE", ZERO, gl, accounts, configured=bool(account_ids),
            detail=[self._detail_row(
                f"CLR_{acc['account_code']}", ZERO,
                gl_by.get(acc["account_id"], ZERO), account=acc,
            ) for acc in accounts],
            variance_breakdown={"uncleared_amount": gl},
        )
        row["exceptions"] = self._suspense_journals(account_ids, location_id, as_of)
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
        raw_valuation_query = self.db.query(func.coalesce(func.sum(
            Inventory.quantity * Inventory.average_cost
        ), 0))
        if location_id is not None:
            raw_valuation_query = raw_valuation_query.join(
                Warehouse, Warehouse.id == Inventory.warehouse_id
            ).filter(Warehouse.location_id == location_id)
        raw_valuation = Decimal(raw_valuation_query.scalar() or 0)
        # Preserve visibility of stock whose product has no inventory account.
        unmapped_stock = raw_valuation - sum(self._inventory_valuation(location_id).values(), ZERO)
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
                                "valuation_method": raw_valuation - sum(ledger_by.values(), ZERO),
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

    def report(self, location_id: int | None = None, date_from: date | None = None,
               date_to: date | None = None) -> dict:
        as_of = date_to
        items = self._snapshot(location_id, as_of)
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
