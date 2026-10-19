"""Read-only financial statements with report layout and comparable periods."""
from calendar import monthrange
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import inspect, func
from sqlalchemy.orm import joinedload
from app.models.budget import Budget, BudgetLine
from app.models.chart_of_account import ChartOfAccount
from app.models.financial_report_setting import FinancialReportSetting
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.opening_balance import OpeningBalance
from app.models.location import Location
from app.models.business_unit import BusinessUnit
from app.models.department import Department
from app.services.financial_statement_service import FinancialStatementService
from app.services.organization_access import effective_business_unit

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
        self._year_evidence = {}
        self._category_mappings = None
        self._accounts = None
        self._report_settings = {}
        self._schema = inspect(db.connection())
        self.report_setup_available = self._schema.has_table("financial_report_settings")
        self.budget_setup_available = all(self._schema.has_table(name) for name in ("budgets", "budget_lines"))

    def budget(self, start, end, scope, budget_id, report_type):
        if not self.budget_setup_available:
            if budget_id is not None:
                raise HTTPException(503, "Budget reporting is awaiting a database update")
            return {}, False
        query = self.db.query(BudgetLine).options(joinedload(BudgetLine.account)).join(Budget, Budget.id == BudgetLine.budget_id).join(ChartOfAccount, ChartOfAccount.id == BudgetLine.account_id)\
            .filter(Budget.status.in_(("APPROVED", "LOCKED")), Budget.fiscal_year == end.year,
                    BudgetLine.month.between(start.month, end.month))
        types = ("REVENUE", "INCOME", "EXPENSE") if report_type == "PROFIT_LOSS" else ("ASSET", "LIABILITY", "EQUITY")
        query = query.filter(ChartOfAccount.account_type.in_(types))
        if budget_id is not None:
            query = query.filter(Budget.id == budget_id)
        for key, value in scope.items():
            if value is not None:
                column = getattr(BudgetLine, key)
                if key == "business_unit_id": column = effective_business_unit(column, BudgetLine.location_id)
                query = query.filter(column.is_(None) if key == "department_id" and value == 0 else column == value)
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

    def _has_year_evidence(self, kind, year, scope):
        key = (kind, year, tuple(scope.items()))
        if key in self._year_evidence:
            return self._year_evidence[key]
        query = self.db.query(JournalLine.id).join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id).filter(
            JournalEntry.status == "POSTED", JournalEntry.posting_date.between(date(year, 1, 1), date(year, 12, 31)),
            JournalEntry.reference_type.notin_(("OPENING_BALANCE", "OPENING_BALANCE_ADJUSTMENT", "PERIOD_CLOSE", "YEAR_END")))
        for name, value in scope.items():
            if value is not None:
                dimension = func.coalesce(getattr(JournalLine, name), getattr(JournalEntry, name))
                if name == "business_unit_id": dimension = effective_business_unit(dimension, func.coalesce(JournalLine.location_id, JournalEntry.location_id))
                query = query.filter(dimension.is_(None) if name == "department_id" and value == 0 else dimension == value)
        available = query.first() is not None
        if not available and kind == "BALANCE_SHEET" and scope["department_id"] is None:
            opening = self.db.query(OpeningBalance.id).filter(OpeningBalance.fiscal_year == year)
            if scope["location_id"] is not None:
                opening = opening.filter(OpeningBalance.location_id == scope["location_id"])
            if scope["business_unit_id"] is not None:
                opening = opening.join(Location, Location.id == OpeningBalance.location_id).filter(Location.business_unit_id == scope["business_unit_id"])
            available = opening.first() is not None
        self._year_evidence[key] = available
        return available

    def build(self, *, report_type, as_of_date, location_id=None, business_unit_id=None,
              department_id=None, budget_id=None, kap=False, include_zero=False, detail=False, all_accounts=False):
        scope = dict(location_id=location_id, business_unit_id=business_unit_id, department_id=department_id)
        calendar = periods(as_of_date)
        values, originals, summaries, budget_available, comparison_available = {}, {}, {}, {}, {}
        for period_name, dates in calendar.items():
            values[period_name], summaries[period_name] = {}, {}
            comparison_available[period_name] = {}
            for metric, (start, end) in dates.items():
                available = metric == "current" or end.year == as_of_date.year or self._has_year_evidence(report_type, end.year, scope)
                comparison_available[period_name][metric] = available
                rows, summary = self._actual(report_type, start, end, scope) if available else ({}, None)
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
        # Layout setup is optional for reading actual balances. During a staged
        # deployment, keep the full ledger readable without creating tables or
        # changing any accounting values. Setup writes still require migration.
        if report_type not in self._report_settings:
            self._report_settings[report_type] = self.db.query(FinancialReportSetting).filter_by(report_type=report_type).first() if self.report_setup_available else None
        settings = self._report_settings[report_type]
        selected = set(settings.selected_account_ids) if not all_accounts and settings and settings.selected_account_ids is not None else None
        if self._accounts is None:
            self._accounts = {a.id: a for a in self.db.query(ChartOfAccount).all()}
        all_accounts = self._accounts
        header_only = False if detail else kap or bool(settings and settings.header_only)
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
            if original.get("includes_unclosed_earnings"):
                row["includes_unclosed_earnings"] = True
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
                for metric in ("last_month", "last_year"):
                    if not comparison_available[period_name][metric]:
                        totals[metric] = None
                totals["variance"] = totals["current"] - totals["budget"] if totals["budget"] is not None else None
        if not include_zero:
            rows = [row for row in rows if any(amount not in (None, ZERO) for totals in row["periods"].values() for amount in totals.values())]
        rows.sort(key=lambda row: (row["section"], row["account_code"], row["account_name"]))
        executive_rows = []
        if report_type == "BALANCE_SHEET":
            from app.services.financial_statement_service import GROUP_LABELS
            buckets = {}
            for key, original in originals.items():
                group = original.get("financial_statement_group") or original["section"]
                bucket = buckets.setdefault((original["section"], group), {
                    "account_code": "", "account_name": GROUP_LABELS.get(group, group.replace("_", " ").title()),
                    "section": original["section"], "account_ids": [],
                    "periods": {p: {metric: ZERO for metric in metrics} for p in calendar}})
                if original["account_id"] is not None: bucket["account_ids"].append(original["account_id"])
                for p in calendar:
                    for metric in metrics: bucket["periods"][p][metric] += values[p][metric].get(key, ZERO)
            for bucket in buckets.values():
                for p in calendar:
                    amounts = bucket["periods"][p]
                    if not budget_available[p]: amounts["budget"] = None
                    for metric in ("last_month", "last_year"):
                        if not comparison_available[p][metric]: amounts[metric] = None
                    amounts["variance"] = amounts["current"] - amounts["budget"] if amounts["budget"] is not None else None
                if include_zero or any(v not in (ZERO, None) for amounts in bucket["periods"].values() for v in amounts.values()):
                    executive_rows.append(bucket)
        sections = ["REVENUE", "COST_OF_REVENUE", "EXPENSES"] if report_type == "PROFIT_LOSS" else ["ASSETS", "LIABILITIES", "EQUITY"]
        # Full-ledger totals remain intact when display setup hides detail rows.
        totals = {}
        for section in sections:
            totals[section] = {p: {} for p in calendar}
            for p in calendar:
                for metric in metrics:
                    if (metric == "budget" and not budget_available[p]) or comparison_available[p].get(metric) is False:
                        total = None
                    else:
                        total = sum((values[p][metric].get(key, ZERO) for key, row in originals.items() if row["section"] == section), ZERO)
                    totals[section][p][metric] = total
                v = totals[section][p]
                v["variance"] = v["current"] - v["budget"] if v["budget"] is not None else None
        scope_labels = {}
        for dimension, model, default in (("location_id", Location, "Consolidated"), ("business_unit_id", BusinessUnit, "All units"), ("department_id", Department, "All departments")):
            record = self.db.get(model, scope[dimension]) if scope[dimension] is not None else None
            scope_labels[dimension] = "Unassigned department" if dimension == "department_id" and scope[dimension] == 0 else record.name if record else default
        report = {"report_type": report_type, "as_of_date": as_of_date, "scope": scope, "scope_labels": scope_labels,
                "periods": calendar, "rows": rows, "executive_rows": executive_rows, "section_totals": totals, "summary": summaries,
                "header_only": header_only, "budget_available": budget_available, "comparison_available": comparison_available,
                "metadata": {"opening_source": "MANUAL_OPENING_BALANCES", "actual_source": "POSTED_JOURNAL_LINES",
                    "report_setup_available": self.report_setup_available, "budget_setup_available": self.budget_setup_available,
                    "display_selection_only": selected is not None, "totals_scope": "COMPLETE_REPORT",
                    "budget_basis": "FULL_MONTH_PLAN" if report_type == "PROFIT_LOSS" else "MONTH_END_BALANCE_TARGET",
                    "closing_entries_excluded_from_profit_loss": True}}
        if report_type == "BALANCE_SHEET":
            position = {section: totals[section]["YTD"]["current"] for section in ("ASSETS", "LIABILITIES", "EQUITY")}
            financing = position["LIABILITIES"] + position["EQUITY"]
            difference = position["ASSETS"] - financing
            report["balance_control"] = {
                "assets": position["ASSETS"], "liabilities_and_equity": financing,
                "difference": difference, "is_balanced": difference == ZERO,
                "basis": "COMPLETE_REPORT", "as_of_date": as_of_date,
            }
        if report_type == "PROFIT_LOSS":
            from app.models.accounting_setting import AccountingSetting
            from app.services.profit_loss_delivery import SETTING_PREFIX, presentation
            if self._category_mappings is None:
                self._category_mappings = {row.account_id: row.description for row in self.db.query(AccountingSetting).filter(AccountingSetting.setting_key.startswith(SETTING_PREFIX)).all()}
            report["include_zero"] = include_zero
            from app.services.profit_loss_relevance import scoped_usage
            evidence = scoped_usage(self.db, scope, as_of_date)
            report["presentation_rows"] = presentation(report, originals, values, all_accounts, self._category_mappings, selected, evidence)
            from app.services.report_statistics import build_statistics
            report["statistics"] = build_statistics(self, report, budget_id)
        return report


    def department_reports(self, report, *, budget_id=None, kap=False, include_zero=False, detail=False, all_accounts=False):
        """One full statement per configured or historically used department.

        Null departmental activity is queried explicitly, never redistributed.
        Inactive departments with historical postings/budgets remain visible.
        """
        from app.models.location_department import LocationDepartment
        scope = report["scope"]
        kind = report["report_type"]
        ids = {0} if kind == "BALANCE_SHEET" and scope["department_id"] is None else set()
        if scope["department_id"] is not None:
            ids.add(scope["department_id"])
        else:
            configured = self.db.query(Department.id).filter(Department.is_active.is_(True))
            if scope["location_id"] is not None:
                configured = configured.join(LocationDepartment).filter(LocationDepartment.location_id == scope["location_id"])
            elif scope["business_unit_id"] is not None:
                configured = configured.filter(Department.business_unit_id == scope["business_unit_id"])
            ids.update(row[0] for row in configured.all())
            activity = self.db.query(func.coalesce(JournalLine.department_id, JournalEntry.department_id)).join(
                JournalEntry, JournalEntry.id == JournalLine.journal_entry_id).join(
                ChartOfAccount, ChartOfAccount.id == JournalLine.account_id).filter(
                JournalEntry.status == "POSTED", ChartOfAccount.account_type.in_(("REVENUE", "INCOME", "EXPENSE") if kind == "PROFIT_LOSS" else ("ASSET","LIABILITY","EQUITY","REVENUE","INCOME","EXPENSE")),
                JournalEntry.posting_date.between(date(report["as_of_date"].year - 1, 1, 1), report["as_of_date"]))
            for name in ("location_id", "business_unit_id"):
                if scope[name] is not None:
                    dimension = func.coalesce(getattr(JournalLine, name), getattr(JournalEntry, name))
                    if name == "business_unit_id": dimension = effective_business_unit(dimension, func.coalesce(JournalLine.location_id, JournalEntry.location_id))
                    activity = activity.filter(dimension == scope[name])
            ids.update(row[0] or 0 for row in activity.distinct().all())
            if self.budget_setup_available:
                budgets = self.db.query(BudgetLine.department_id).join(Budget).filter(
                    Budget.fiscal_year == report["as_of_date"].year, Budget.status.in_(("APPROVED", "LOCKED")))
                if budget_id is not None:
                    budgets = budgets.filter(Budget.id == budget_id)
                for name in ("location_id", "business_unit_id"):
                    if scope[name] is not None:
                        dimension = getattr(BudgetLine, name)
                        if name == "business_unit_id": dimension = effective_business_unit(dimension, BudgetLine.location_id)
                        budgets = budgets.filter(dimension == scope[name])
                ids.update(row[0] or 0 for row in budgets.distinct().all())
        names = {row.id: row.name for row in self.db.query(Department).filter(Department.id.in_(ids)).all()}
        result = []
        for dept_id in sorted(ids, key=lambda value: (value == 0, names.get(value, ""))):
            child = self.build(report_type=kind, as_of_date=report["as_of_date"],
                location_id=scope["location_id"], business_unit_id=scope["business_unit_id"],
                department_id=dept_id, budget_id=budget_id, kap=kap, include_zero=include_zero, detail=detail, all_accounts=all_accounts)
            result.append({"department_id": dept_id or None, "department_name": names.get(dept_id, "Unassigned department"),
                           "rows": child["rows"], "related_accounts": child.get("related_accounts",[]), "section_totals": child["section_totals"],
                           "statistics": child.get("statistics"), "periods": child["periods"], "presentation_rows": child.get("presentation_rows",[]), "comparison_available": child["comparison_available"]})
        return result
