"""Read-only financial statements with report layout and comparable periods."""
from calendar import monthrange
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from app.models.budget import Budget, BudgetLine
from app.models.chart_of_account import ChartOfAccount
from app.models.financial_report_setting import FinancialReportSetting
from app.services.financial_statement_service import FinancialStatementService

ZERO = Decimal("0")
METRICS = ("current", "budget", "last_month", "last_year")


def shifted(value: date, *, months=0, years=0) -> date:
    ordinal = value.year * 12 + value.month - 1 + months + years * 12
    year, month = divmod(ordinal, 12)
    return date(year, month + 1, min(value.day, monthrange(year, month + 1)[1]))


def periods(as_of: date) -> dict:
    # Last-month and prior-year comparisons use the same elapsed day count;
    # February and leap-year boundaries are clipped to valid dates.
    previous, last_year = shifted(as_of, months=-1), shifted(as_of, years=-1)
    return {
        "MTD": {"current": (as_of.replace(day=1), as_of),
                "last_month": (previous.replace(day=1), previous),
                "last_year": (last_year.replace(day=1), last_year)},
        "YTD": {"current": (date(as_of.year, 1, 1), as_of),
                "last_month": (date(previous.year, 1, 1), previous),
                "last_year": (date(last_year.year, 1, 1), last_year)},
    }


class FinancialReportingService:
    def __init__(self, db):
        self.db = db
        self.statements = FinancialStatementService(db)
        self._actual_cache = {}

    def budget(self, start, end, scope, budget_id, report_type):
        query = self.db.query(BudgetLine).options(joinedload(BudgetLine.account)).join(Budget, Budget.id == BudgetLine.budget_id).join(ChartOfAccount, ChartOfAccount.id == BudgetLine.account_id)\
            .filter(Budget.status.in_(("APPROVED", "LOCKED")), Budget.fiscal_year == end.year,
                    BudgetLine.month.between(start.month, end.month))
        types = ("REVENUE", "INCOME", "EXPENSE") if report_type == "PROFIT_LOSS" else ("ASSET", "LIABILITY", "EQUITY")
        query = query.filter(ChartOfAccount.account_type.in_(types))
        if budget_id is not None:
            query = query.filter(Budget.id == budget_id)
        for key, value in scope.items():
            if value is not None:
                query = query.filter(getattr(BudgetLine, key) == value)
        if report_type == "BALANCE_SHEET":
            # A balance-sheet budget is a monthly closing target, not a flow.
            query = query.filter(BudgetLine.month == end.month)
        rows = query.all()
        seen, amounts = set(), defaultdict(lambda: ZERO)
        for line in rows:
            dimension = (line.month, line.account_id, line.business_unit_id, line.location_id, line.department_id)
            if dimension in seen:
                raise HTTPException(422, "Approved budgets overlap. Select a single budget for this report")
            seen.add(dimension)
            amount = Decimal(line.budget_amount)
            if report_type == "BALANCE_SHEET":
                expected = "DEBIT" if line.account.account_type == "ASSET" else "CREDIT"
                amount *= 1 if line.account.normal_balance == expected else -1
            amounts[line.account_id] += amount
        return dict(amounts), bool(rows)

    def _actual(self, kind, start, end, scope):
        cache_key = (kind, start if kind == "PROFIT_LOSS" else None, end, tuple(scope.items()))
        if cache_key in self._actual_cache:
            return self._actual_cache[cache_key]
        if kind == "PROFIT_LOSS":
            report = self.statements.profit_and_loss(date_from=start, date_to=end, include_zero_balance=True, include_inactive=True, **scope)
            field = "current_amount"
        else:
            report = self.statements.balance_sheet(as_of_date=end, include_zero_balance=True, include_inactive=True, **scope)
            field = "closing_amount"
        accounts = {}
        for section in report["sections"]:
            for group in section["groups"]:
                for row in group["accounts"]:
                    key = row["account_id"] if row["account_id"] is not None else "earnings:" + row["financial_statement_group"]
                    accounts[key] = {**row, "section": section["code"], "amount": row[field]}
        self._actual_cache[cache_key] = (accounts, report["summary"])
        return self._actual_cache[cache_key]

    def build(self, *, report_type, as_of_date, location_id=None, business_unit_id=None,
              department_id=None, budget_id=None, kap=False, include_zero=False):
        scope = dict(location_id=location_id, business_unit_id=business_unit_id, department_id=department_id)
        calendar = periods(as_of_date)
        values, originals, summaries, budget_available = {}, {}, {}, {}
        for period_name, dates in calendar.items():
            values[period_name], summaries[period_name] = {}, {}
            for metric, (start, end) in dates.items():
                rows, summary = self._actual(report_type, start, end, scope)
                originals.update(rows)
                values[period_name][metric] = {key: row["amount"] for key, row in rows.items()}
                summaries[period_name][metric] = summary
            start, end = dates["current"]
            amounts, available = self.budget(start, end, scope, budget_id, report_type)
            values[period_name]["budget"] = amounts
            budget_available[period_name] = available
            if report_type == "BALANCE_SHEET":
                current_rows, _ = self._actual(report_type, start, end, scope)
                if start.month == 1:
                    beginning = {key: row.get("opening_amount", ZERO) for key, row in current_rows.items()}
                else:
                    prior_rows, _ = self._actual(report_type, start, start - timedelta(days=1), scope)
                    beginning = {key: row["amount"] for key, row in prior_rows.items()}
                values[period_name]["movement"] = {key: row["amount"] - beginning.get(key, ZERO) for key, row in current_rows.items()}
            # Include budget-only accounts in the comparison, even with no posting.
            for account_id in amounts:
                if account_id in originals:
                    continue
                account = self.db.get(ChartOfAccount, account_id)
                section = ("REVENUE" if account.account_type in ("REVENUE", "INCOME") else
                           "COST_OF_REVENUE" if account.financial_statement_group == "COST_OF_REVENUE" else "EXPENSES") if report_type == "PROFIT_LOSS" else {"ASSET": "ASSETS", "LIABILITY": "LIABILITIES", "EQUITY": "EQUITY"}[account.account_type]
                originals[account_id] = dict(account_id=account_id, account_code=account.account_number,
                    account_name=account.account_name, parent_account_id=account.parent_account_id,
                    account_type=account.account_type, section=section)
        metrics = METRICS + (("movement",) if report_type == "BALANCE_SHEET" else ())
        settings = self.db.query(FinancialReportSetting).filter_by(report_type=report_type).first()
        selected = set(settings.selected_account_ids) if settings and settings.selected_account_ids is not None else None
        all_accounts = {a.id: a for a in self.db.query(ChartOfAccount).all()}
        header_only = kap or bool(settings and settings.header_only)
        display = {}
        for key, original in originals.items():
            account = all_accounts.get(original["account_id"])
            ancestors = []
            current, visited = account, set()
            while current and current.id not in visited:
                ancestors.append(current.id)
                visited.add(current.id)
                current = all_accounts.get(current.parent_account_id)
            if selected is not None and not selected.intersection(ancestors):
                continue
            # All revenue is delivered as one 400 line, including legacy history.
            if original["account_type"] in ("REVENUE", "INCOME"):
                display_key, code, name, section = "revenue:400", "400", "Pendapatan", "REVENUE"
            elif header_only and account and account.parent_account_id:
                parent = all_accounts[account.parent_account_id]
                display_key, code, name, section = (original["section"], parent.id), parent.account_number, parent.account_name, original["section"]
            elif header_only:
                # Standalone posting accounts and computed earnings belong to
                # their section header; KAP never exposes a stray detail row.
                section = original["section"]
                display_key, code, name = (section, "standalone"), "", {
                    "ASSETS": "Assets", "LIABILITIES": "Liabilities", "EQUITY": "Equity",
                    "COST_OF_REVENUE": "Cost of Revenue", "EXPENSES": "Expenses"}[section]
            else:
                display_key, code, name, section = key, original["account_code"], original["account_name"], original["section"]
            row = display.setdefault(display_key, {"account_code": code, "account_name": name, "section": section,
                "account_ids": [], "periods": {p: {metric: ZERO for metric in metrics} for p in calendar}})
            if original["account_id"] is not None:
                row["account_ids"].append(original["account_id"])
            for period_name in calendar:
                for metric in metrics:
                    row["periods"][period_name][metric] += values[period_name][metric].get(key, ZERO)
        rows = list(display.values())
        for row in rows:
            for period_name in calendar:
                totals = row["periods"][period_name]
                if not budget_available[period_name]:
                    totals["budget"] = None
                totals["variance"] = totals["current"] - totals["budget"] if totals["budget"] is not None else None
        if not include_zero:
            rows = [row for row in rows if any(amount not in (None, ZERO) for totals in row["periods"].values() for amount in totals.values())]
        rows.sort(key=lambda row: (row["section"], row["account_code"], row["account_name"]))
        sections = ["REVENUE", "COST_OF_REVENUE", "EXPENSES"] if report_type == "PROFIT_LOSS" else ["ASSETS", "LIABILITIES", "EQUITY"]
        # Full-ledger totals remain intact when display setup hides detail rows.
        totals = {}
        for section in sections:
            totals[section] = {p: {} for p in calendar}
            for p in calendar:
                for metric in metrics:
                    if metric == "budget" and not budget_available[p]:
                        total = None
                    else:
                        total = sum((values[p][metric].get(key, ZERO) for key, row in originals.items() if row["section"] == section), ZERO)
                    totals[section][p][metric] = total
                v = totals[section][p]
                v["variance"] = v["current"] - v["budget"] if v["budget"] is not None else None
        return {"report_type": report_type, "as_of_date": as_of_date, "scope": scope,
                "periods": calendar, "rows": rows, "section_totals": totals, "summary": summaries,
                "header_only": header_only, "budget_available": budget_available,
                "metadata": {"opening_source": "MANUAL_OPENING_BALANCES", "actual_source": "POSTED_JOURNAL_LINES",
                    "display_selection_only": selected is not None, "totals_scope": "COMPLETE_REPORT",
                    "budget_basis": "FULL_MONTH_PLAN" if report_type == "PROFIT_LOSS" else "MONTH_END_BALANCE_TARGET",
                    "closing_entries_excluded_from_profit_loss": True}}
