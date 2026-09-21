from datetime import datetime, timezone

from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.account_receivable import AccountReceivable
from app.models.accounting_posting_rule import AccountingPostingRule
from app.models.chart_of_account import ChartOfAccount
from app.models.inventory import Inventory
from app.models.warehouse import Warehouse
from app.models.stock_movement import StockMovement
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

    def _gl_balance(self, account_ids: list[int], location_id: int | None = None) -> Decimal:
        return sum(self._gl_by_account(account_ids, location_id).values(), ZERO)

    def _gl_by_account(self, account_ids: list[int], location_id: int | None = None) -> dict[int, Decimal]:
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
        result = {}
        for account_id, normal_balance, debit, credit in query.all():
            debit = Decimal(debit or 0)
            credit = Decimal(credit or 0)
            result[account_id] = credit - debit if normal_balance == "CREDIT" else debit - credit
        return result

    def _stock_ledger(self, account_ids: list[int] | None, location_id: int | None = None) -> dict[int, Decimal]:
        """Subledger value per inventory account from stock movements (IN/OUT).

        account_ids=None means "all inventory posting accounts" — the union is
        used to scope the GL side so every account the goods-receipt engine
        posts to is included in the control.
        """
        query = (
            self.db.query(
                StockMovement.inventory_account_id,
                func.coalesce(func.sum(StockMovement.quantity * StockMovement.unit_cost), 0),
            )
            .filter(StockMovement.inventory_account_id.is_not(None))
            .group_by(StockMovement.inventory_account_id)
        )
        if account_ids:
            query = query.filter(StockMovement.inventory_account_id.in_(account_ids))
        if location_id is not None:
            query = query.join(Warehouse, Warehouse.id == StockMovement.warehouse_id).filter(
                Warehouse.location_id == location_id
            )
        return {account_id: Decimal(value) for account_id, value in query.all()}

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

    def accounts_payable(self, location_id: int | None = None) -> dict:
        # SupplierInvoice is authoritative. account_payables is a compatibility
        # mirror and has its own exception checker in ap_reconciliation.
        source_query = self.db.query(func.coalesce(func.sum(SupplierInvoice.balance_amount), 0)).filter(
            SupplierInvoice.status == "POSTED"
        )
        if location_id is not None:
            source_query = source_query.filter(SupplierInvoice.location_id == location_id)
        source = Decimal(source_query.scalar() or 0)
        account_ids = self._rule_account_ids(
            debit=False,
            event_types=["SUPPLIER_INVOICE_INVENTORY", "SUPPLIER_INVOICE_DIRECT_USE"],
            location_id=location_id,
        )
        gl_by = self._gl_by_account(account_ids, location_id)
        gl = sum(gl_by.values(), ZERO)
        detail = [
            self._detail_row(
                f"AP_{acc['account_code']}",
                gl_by.get(acc["account_id"], ZERO),
                gl_by.get(acc["account_id"], ZERO),
                account=acc,
            )
            for acc in self._accounts(account_ids)
        ]
        return self._row(
            "ACCOUNTS_PAYABLE",
            source,
            gl,
            self._accounts(account_ids),
            configured=bool(account_ids),
            detail=detail,
            variance_breakdown={"posting_mismatch": source - gl},
        )

    def accounts_receivable(self, location_id: int | None = None) -> dict:
        if location_id is not None:
            # The legacy AR subledger has no location dimension yet. Never leak
            # global AR totals into a location-scoped reconciliation response.
            return self._row("ACCOUNTS_RECEIVABLE", ZERO, ZERO, [], configured=False)
        source = Decimal(
            self.db.query(func.coalesce(func.sum(AccountReceivable.outstanding_amount), 0)).scalar()
            or 0
        )
        # CUSTOMER_PAYMENT identifies the canonical AR control account on
        # the credit side. Missing invoice-side postings remain visible as an
        # out-of-balance result instead of being hidden by account guessing.
        account_ids = self._rule_account_ids(
            debit=False,
            event_types=["CUSTOMER_PAYMENT"],
        )
        gl = self._gl_balance(account_ids, location_id)
        return self._row(
            "ACCOUNTS_RECEIVABLE",
            source,
            gl,
            self._accounts(account_ids),
            configured=bool(account_ids),
            variance_breakdown={"posting_mismatch": source - gl},
        )

    def clearing_suspense(self, location_id: int | None = None) -> dict:
        """Pass-through/suspense accounts must net to zero (e.g. AP Suspense)."""
        query = self.db.query(ChartOfAccount).filter(
            ChartOfAccount.account_name.ilike("%suspense%"),
            ChartOfAccount.is_active.is_(True),
        )
        rows = query.order_by(ChartOfAccount.account_number).all()
        account_ids = [row.id for row in rows]
        if not account_ids:
            return self._row("CLEARING_SUSPENSE", ZERO, ZERO, [], configured=False)
        gl_by = self._gl_by_account(account_ids, location_id)
        gl = sum(gl_by.values(), ZERO)
        detail = [
            self._detail_row(
                f"CLR_{acc.account_number}",
                gl_by.get(acc.id, ZERO),
                gl_by.get(acc.id, ZERO),
                account={
                    "account_id": acc.id,
                    "account_code": acc.account_number,
                    "account_name": acc.account_name,
                    "normal_balance": acc.normal_balance,
                },
            )
            for acc in rows
        ]
        return self._row(
            "CLEARING_SUSPENSE",
            ZERO,
            gl,
            [
                {
                    "account_id": row.id,
                    "account_code": row.account_number,
                    "account_name": row.account_name,
                    "normal_balance": row.normal_balance,
                }
                for row in rows
            ],
            configured=bool(account_ids),
            detail=detail,
            variance_breakdown={"uncleared_amount": gl},
        )

    def inventory(self, location_id: int | None = None) -> dict:
        # Inventory posting accounts: every account the goods-receipt engine
        # actually debited (from stock movements), plus the rule-configured one.
        rule_ids = self._rule_account_ids(
            debit=True,
            event_types=["SUPPLIER_INVOICE_INVENTORY"],
            location_id=location_id,
        )
        ledger_by = self._stock_ledger(None, location_id)
        account_ids = sorted(set(rule_ids) | set(ledger_by.keys()))
        ledger = sum(ledger_by.values(), ZERO)
        gl_by = self._gl_by_account(account_ids, location_id)
        gl = sum(gl_by.values(), ZERO)
        diff = ledger - gl

        account_meta = self._accounts_by_id(account_ids)
        detail = []
        for account_id in sorted(account_ids, key=lambda aid: (account_meta.get(aid, {}).get("account_code") or "", aid)):
            acc = account_meta.get(account_id, {"account_code": str(account_id), "account_name": str(account_id)})
            ledger_a = ledger_by.get(account_id, ZERO)
            gl_a = gl_by.get(account_id, ZERO)
            detail.append(self._detail_row(f"INV_{acc['account_code']}", ledger_a, gl_a, account=acc))

        # Valuation check: running avg-cost snapshot vs posted subledger value.
        val_query = self.db.query(
            func.coalesce(func.sum(Inventory.quantity * Inventory.average_cost), 0)
        )
        if location_id is not None:
            val_query = val_query.join(Warehouse, Warehouse.id == Inventory.warehouse_id).filter(
                Warehouse.location_id == location_id
            )
        valuation = Decimal(val_query.scalar() or 0).quantize(Decimal("0.01"))
        valuation_drift = valuation - ledger
        detail.append({
            "control": "VALUATION_AVG_COST",
            "external_statement": valuation,
            "gl_balance": ledger,
            "variance": valuation_drift,
            "status": "RECONCILED" if valuation_drift == ZERO else "VALUATION_DRIFT",
            "visual": "GREEN" if valuation_drift == ZERO else "AMBER",
            "account_code": None,
            "account_name": "Stock value at average cost (roof: subledger value)",
            "configured": True,
        })

        return self._row(
            "INVENTORY",
            ledger,
            gl,
            self._accounts(account_ids),
            configured=bool(account_ids),
            detail=detail,
            variance_breakdown={
                "posting_mismatch": diff,
                "valuation_method": valuation_drift,
            },
        )

    def report(self, location_id: int | None = None) -> dict:
        items = [
            self.accounts_payable(location_id),
            self.accounts_receivable(location_id),
            self.clearing_suspense(location_id),
            self.inventory(location_id),
        ]
        total_variance = sum(
            (row["variance"] for row in items if row["status"] in ("OUT_OF_BALANCE",)),
            ZERO,
        )
        return {
            "items": items,
            "summary": {
                "reconciled": sum(row["status"] == "RECONCILED" for row in items),
                "out_of_balance": sum(row["status"] == "OUT_OF_BALANCE" for row in items),
                "not_configured": sum(row["status"] == "NOT_CONFIGURED" for row in items),
                "ready_to_close": all(
                    row["status"] in ("RECONCILED",) for row in items
                ),
                "variance_tracker": {
                    "total_variance": total_variance,
                    "checks": len(items),
                    "green": sum(row["visual"] == "GREEN" for row in items),
                    "amber": sum(row["visual"] == "AMBER" for row in items),
                    "red": sum(row["visual"] == "RED" for row in items),
                },
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            "scope": "CURRENT_BALANCE",
            "read_only": True,
        }