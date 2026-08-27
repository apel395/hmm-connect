from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.account_receivable import AccountReceivable
from app.models.accounting_posting_rule import AccountingPostingRule
from app.models.chart_of_account import ChartOfAccount
from app.models.inventory import Inventory
from app.models.warehouse import Warehouse
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.supplier_invoice import SupplierInvoice

ZERO = Decimal("0.00")


class FinancialReconciliationService:
    """Read-only controls comparing current subledger balances with posted GL balances."""

    def __init__(self, db: Session):
        self.db = db

    def _gl_balance(self, account_ids: list[int], location_id: int | None = None) -> Decimal:
        if not account_ids:
            return ZERO
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
        rows = query.all()
        total = ZERO
        for _, normal_balance, debit, credit in rows:
            debit = Decimal(debit or 0)
            credit = Decimal(credit or 0)
            total += credit - debit if normal_balance == "CREDIT" else debit - credit
        return total

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
    def _row(
        control: str,
        source: Decimal,
        gl: Decimal,
        accounts: list[dict],
        configured: bool = True,
    ) -> dict:
        difference = source - gl
        if not configured:
            status = "NOT_CONFIGURED"
        else:
            status = "RECONCILED" if difference == ZERO else "OUT_OF_BALANCE"
        return {
            "control": control,
            "source_balance": source,
            "gl_balance": gl,
            "difference": difference,
            "status": status,
            "accounts": accounts,
        }

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
        return self._row(
            "ACCOUNTS_PAYABLE",
            source,
            self._gl_balance(account_ids, location_id),
            self._accounts(account_ids),
            configured=bool(account_ids),
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
        return self._row(
            "ACCOUNTS_RECEIVABLE",
            source,
            self._gl_balance(account_ids, location_id),
            self._accounts(account_ids),
            configured=bool(account_ids),
        )

    def inventory(self, location_id: int | None = None) -> dict:
        source_query = self.db.query(
            func.coalesce(func.sum(Inventory.quantity * Inventory.average_cost), 0)
        )
        if location_id is not None:
            source_query = source_query.join(Warehouse, Warehouse.id == Inventory.warehouse_id).filter(
                Warehouse.location_id == location_id
            )
        source_raw = source_query.scalar()
        source = Decimal(source_raw or 0).quantize(Decimal("0.01"))
        account_ids = self._rule_account_ids(
            debit=True,
            event_types=["SUPPLIER_INVOICE_INVENTORY"],
            location_id=location_id,
        )
        return self._row(
            "INVENTORY",
            source,
            self._gl_balance(account_ids, location_id),
            self._accounts(account_ids),
            configured=bool(account_ids),
        )

    def report(self, location_id: int | None = None) -> dict:
        items = [
            self.accounts_payable(location_id),
            self.accounts_receivable(location_id),
            self.inventory(location_id),
        ]
        return {
            "items": items,
            "summary": {
                "reconciled": sum(row["status"] == "RECONCILED" for row in items),
                "out_of_balance": sum(row["status"] == "OUT_OF_BALANCE" for row in items),
                "not_configured": sum(row["status"] == "NOT_CONFIGURED" for row in items),
            },
            "scope": "CURRENT_BALANCE",
            "read_only": True,
        }
