from datetime import date
from decimal import Decimal
from math import ceil

from sqlalchemy import exists, func, or_
from sqlalchemy.orm import Session

from app.models.chart_of_account import ChartOfAccount
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine


ZERO = Decimal("0.00")


class TrialBalanceService:
    SORT_FIELDS = {
        "account_code": lambda row: row["account_code"],
        "account_name": lambda row: row["account_name"].lower(),
        "account_type": lambda row: (row["account_type"], row["account_code"]),
        "opening_balance": lambda row: row["opening_balance"],
        "period_debit": lambda row: row["period_debit"],
        "period_credit": lambda row: row["period_credit"],
        "period_total": lambda row: row["period_total"],
        "closing_balance": lambda row: row["closing_balance"],
    }

    def __init__(self, db: Session):
        self.db = db

    def _activity(self, *, date_from: date | None = None, date_to: date | None = None, before: date | None = None, location_id: int | None = None, department_id: int | None = None, business_unit_id: int | None = None) -> dict[int, tuple[Decimal, Decimal]]:
        query = self.db.query(JournalLine.account_id, func.coalesce(func.sum(JournalLine.debit), 0), func.coalesce(func.sum(JournalLine.credit), 0)).join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id).filter(JournalEntry.status == "POSTED")
        if before: query = query.filter(JournalEntry.posting_date < before)
        if date_from: query = query.filter(JournalEntry.posting_date >= date_from)
        if date_to: query = query.filter(JournalEntry.posting_date <= date_to)
        if location_id: query = query.filter(JournalLine.location_id == location_id)
        if department_id: query = query.filter(JournalLine.department_id == department_id)
        if business_unit_id: query = query.filter(JournalLine.business_unit_id == business_unit_id)
        return {account_id: (Decimal(debit), Decimal(credit)) for account_id, debit, credit in query.group_by(JournalLine.account_id).all()}

    @staticmethod
    def _normal_balance_amount(normal_balance: str, debit: Decimal, credit: Decimal) -> Decimal:
        return credit - debit if normal_balance == "CREDIT" else debit - credit

    def report(self, *, date_from: date, date_to: date, page: int = 1, page_size: int = 50, search: str | None = None, account_type: str | None = None, account_id: int | None = None, parent_account_id: int | None = None, include_zero_balance: bool = False, include_inactive: bool = False, location_id: int | None = None, department_id: int | None = None, business_unit_id: int | None = None, sort_by: str = "account_code", sort_order: str = "asc", paginate: bool = True) -> dict:
        if date_from > date_to: raise ValueError("date_from must be on or before date_to")

        child = ChartOfAccount.__table__.alias("trial_balance_child")
        has_child = exists().where(child.c.parent_account_id == ChartOfAccount.id)
        accounts_query = self.db.query(ChartOfAccount).filter(ChartOfAccount.is_posting.is_(True), ~has_child)
        if not include_inactive: accounts_query = accounts_query.filter(ChartOfAccount.is_active.is_(True))
        if search:
            term = f"%{search.strip()}%"
            accounts_query = accounts_query.filter(or_(ChartOfAccount.account_number.ilike(term), ChartOfAccount.account_name.ilike(term)))
        if account_type: accounts_query = accounts_query.filter(ChartOfAccount.account_type == account_type.upper())
        if account_id: accounts_query = accounts_query.filter(ChartOfAccount.id == account_id)
        if parent_account_id: accounts_query = accounts_query.filter(ChartOfAccount.parent_account_id == parent_account_id)

        opening = self._activity(before=date_from, location_id=location_id, department_id=department_id, business_unit_id=business_unit_id)
        period = self._activity(date_from=date_from, date_to=date_to, location_id=location_id, department_id=department_id, business_unit_id=business_unit_id)
        rows = []
        for account in accounts_query.all():
            od, oc = opening.get(account.id, (ZERO, ZERO)); pd, pc = period.get(account.id, (ZERO, ZERO))
            opening_balance = self._normal_balance_amount(account.normal_balance, od, oc)
            period_total = self._normal_balance_amount(account.normal_balance, pd, pc)
            closing_balance = opening_balance + period_total
            status = "ABNORMAL" if closing_balance < ZERO else "NORMAL"
            if not include_zero_balance and not any((od, oc, pd, pc)): continue
            rows.append({"account_id": account.id, "account_code": account.account_number, "account_name": account.account_name, "account_type": account.account_type, "normal_balance": account.normal_balance, "financial_statement_group": account.financial_statement_group, "parent_account_id": account.parent_account_id, "parent_account_code": account.parent.account_number if account.parent else None, "parent_account_name": account.parent.account_name if account.parent else None, "opening_balance": opening_balance, "period_debit": pd, "period_credit": pc, "period_total": period_total, "closing_balance": closing_balance, "status": status, "is_abnormal_balance": status == "ABNORMAL"})

        key = self.SORT_FIELDS.get(sort_by, self.SORT_FIELDS["account_code"]); rows.sort(key=key, reverse=sort_order.lower() == "desc")
        summary = {"opening_balance": sum((r["opening_balance"] for r in rows), ZERO), "period_debit": sum((r["period_debit"] for r in rows), ZERO), "period_credit": sum((r["period_credit"] for r in rows), ZERO), "period_total": sum((r["period_total"] for r in rows), ZERO), "closing_balance": sum((r["closing_balance"] for r in rows), ZERO)}
        summary["difference"] = summary["period_debit"] - summary["period_credit"]; summary["is_balanced"] = summary["difference"] == ZERO; summary["account_count"] = len(rows); summary["abnormal_balance_count"] = sum(r["is_abnormal_balance"] for r in rows)
        total = len(rows); items = rows[(page - 1) * page_size:page * page_size] if paginate else rows
        return {"items": items, "summary": summary, "page": page, "page_size": page_size, "total_items": total, "total_pages": ceil(total / page_size) if total else 0, "has_next": paginate and page * page_size < total, "has_previous": paginate and page > 1}
