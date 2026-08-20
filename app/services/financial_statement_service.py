from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.services.trial_balance_service import TrialBalanceService, ZERO


BALANCE_GROUPS = {
    "ASSET": ("CURRENT_ASSET", "NON_CURRENT_ASSET", "UNCLASSIFIED_ASSET"),
    "LIABILITY": ("CURRENT_LIABILITY", "NON_CURRENT_LIABILITY", "UNCLASSIFIED_LIABILITY"),
    "EQUITY": ("EQUITY", "UNCLASSIFIED_EQUITY"),
}
GROUP_LABELS = {
    "CURRENT_ASSET": "Current Assets", "NON_CURRENT_ASSET": "Non-current Assets",
    "UNCLASSIFIED_ASSET": "Unclassified Assets", "CURRENT_LIABILITY": "Current Liabilities",
    "NON_CURRENT_LIABILITY": "Non-current Liabilities", "UNCLASSIFIED_LIABILITY": "Unclassified Liabilities",
    "EQUITY": "Equity", "UNCLASSIFIED_EQUITY": "Unclassified Equity",
    "CURRENT_PERIOD_EARNINGS": "Current Period Earnings", "OPERATING_REVENUE": "Operating Revenue",
    "OTHER_REVENUE": "Other Revenue", "UNCLASSIFIED_REVENUE": "Unclassified Revenue",
    "COST_OF_REVENUE": "Cost of Revenue", "OPERATING_EXPENSE": "Operating Expenses",
    "OTHER_EXPENSE": "Other Expenses", "UNCLASSIFIED_EXPENSE": "Unclassified Expenses",
}


class FinancialStatementService:
    def __init__(self, db: Session):
        self.db = db
        self.trial = TrialBalanceService(db)

    def _trial(self, date_from: date, date_to: date, **filters) -> list[dict]:
        return self.trial.report(
            date_from=date_from, date_to=date_to, include_zero_balance=True,
            paginate=False, page_size=200, **filters,
        )["items"]

    @staticmethod
    def _variance(current: Decimal, comparative: Decimal | None) -> tuple[Decimal | None, Decimal | None]:
        if comparative is None:
            return None, None
        variance = current - comparative
        percentage = variance / abs(comparative) * Decimal("100") if comparative != ZERO else None
        return variance, percentage

    @staticmethod
    def _net(row: dict) -> Decimal:
        """Return legacy debit-minus-credit sign from canonical closing_balance.

        Trial Balance now exposes one normal-balance-adjusted closing value
        instead of closing_debit/closing_credit. Balance Sheet still needs the
        legacy signed value internally: debit-normal is positive and
        credit-normal is negative.
        """
        balance = Decimal(row.get("closing_balance") or ZERO)
        return balance if row.get("normal_balance") != "CREDIT" else -balance

    @staticmethod
    def _period_amount(row: dict) -> Decimal:
        return row["period_credit"] - row["period_debit"] if row["account_type"] == "REVENUE" else row["period_debit"] - row["period_credit"]

    def _filters(self, account_id, parent_account_id, include_inactive, location_id, department_id, business_unit_id=None):
        return {
            "account_id": account_id, "parent_account_id": parent_account_id,
            "include_inactive": include_inactive, "location_id": location_id,
            "department_id": department_id,
            "business_unit_id": business_unit_id,
        }

    def earnings(self, as_of_date: date, **filters) -> Decimal:
        rows = self._trial(date(as_of_date.year, 1, 1), as_of_date, **filters)
        revenue = sum((self._period_amount(row) for row in rows if row["account_type"] == "REVENUE"), ZERO)
        expense = sum((self._period_amount(row) for row in rows if row["account_type"] == "EXPENSE"), ZERO)
        return revenue - expense

    def balance_sheet(
        self, *, as_of_date: date, comparative_date: date | None = None,
        account_id=None, parent_account_id=None, location_id=None, department_id=None, business_unit_id=None,
        include_zero_balance=False, include_inactive=False, detail_level="DETAIL",
    ) -> dict:
        filters = self._filters(account_id, parent_account_id, include_inactive, location_id, department_id, business_unit_id)
        current_rows = self._trial(date(as_of_date.year, 1, 1), as_of_date, **filters)
        comparative_rows = self._trial(date(comparative_date.year, 1, 1), comparative_date, **filters) if comparative_date else []
        comparisons = {row["account_id"]: row for row in comparative_rows}
        groups = {code: [] for values in BALANCE_GROUPS.values() for code in values}
        unclassified = 0
        for row in current_rows:
            account_type = row["account_type"]
            if account_type not in BALANCE_GROUPS:
                continue
            net = self._net(row)
            amount = net if account_type == "ASSET" else -net
            comp_row = comparisons.get(row["account_id"])
            comp_net = self._net(comp_row) if comp_row else ZERO
            comparative = (comp_net if account_type == "ASSET" else -comp_net) if comparative_date else None
            if not include_zero_balance and amount == ZERO and (comparative is None or comparative == ZERO):
                continue
            configured = row.get("financial_statement_group")
            allowed = set(BALANCE_GROUPS[account_type][:-1] if account_type != "EQUITY" else ("EQUITY",))
            group = configured if configured in allowed else BALANCE_GROUPS[account_type][-1]
            if group.startswith("UNCLASSIFIED"):
                unclassified += 1
            variance, percentage = self._variance(amount, comparative)
            groups[group].append({**row, "current_amount": amount, "comparative_amount": comparative, "variance_amount": variance, "variance_percentage": percentage})

        current_earnings = self.earnings(as_of_date, **filters)
        comparative_earnings = self.earnings(comparative_date, **filters) if comparative_date else None
        variance, percentage = self._variance(current_earnings, comparative_earnings)
        groups["EQUITY"].append({
            "account_id": None, "account_code": "", "account_name": "Current Period Earnings",
            "account_type": "EQUITY", "parent_account_id": None,
            "financial_statement_group": "CURRENT_PERIOD_EARNINGS", "current_amount": current_earnings,
            "comparative_amount": comparative_earnings, "variance_amount": variance,
            "variance_percentage": percentage, "is_synthetic": True,
        })
        section_specs = [("ASSETS", "Assets", "ASSET"), ("LIABILITIES", "Liabilities", "LIABILITY"), ("EQUITY", "Equity", "EQUITY")]
        sections = []
        for section_code, section_label, account_type in section_specs:
            section_groups = []
            for group_code in BALANCE_GROUPS[account_type]:
                accounts = sorted(groups[group_code], key=lambda row: row["account_code"])
                total = sum((row["current_amount"] for row in accounts), ZERO)
                comparative_total = sum((row["comparative_amount"] or ZERO for row in accounts), ZERO) if comparative_date else None
                group_variance, group_percentage = self._variance(total, comparative_total)
                if accounts or include_zero_balance:
                    section_groups.append({"code": group_code, "label": GROUP_LABELS[group_code], "accounts": accounts if detail_level == "DETAIL" else [], "total": total, "comparative_total": comparative_total, "variance_amount": group_variance, "variance_percentage": group_percentage})
            if account_type == "EQUITY":
                accounts = groups["EQUITY"]
                if detail_level == "SUMMARY":
                    target = next((group for group in section_groups if group["code"] == "EQUITY"), None)
                    if target:
                        target["accounts"] = []
            total = sum((group["total"] for group in section_groups), ZERO)
            comparative_total = sum((group["comparative_total"] or ZERO for group in section_groups), ZERO) if comparative_date else None
            section_variance, section_percentage = self._variance(total, comparative_total)
            sections.append({"code": section_code, "label": section_label, "groups": section_groups, "total": total, "comparative_total": comparative_total, "variance_amount": section_variance, "variance_percentage": section_percentage})
        totals = {section["code"]: section["total"] for section in sections}
        liabilities_equity = totals["LIABILITIES"] + totals["EQUITY"]
        difference = totals["ASSETS"] - liabilities_equity
        return {
            "as_of_date": as_of_date, "comparative_date": comparative_date, "detail_level": detail_level,
            "sections": sections,
            "summary": {"total_assets": totals["ASSETS"], "total_liabilities": totals["LIABILITIES"], "total_equity": totals["EQUITY"], "current_period_earnings": current_earnings, "total_liabilities_and_equity": liabilities_equity, "difference": difference, "is_balanced": difference == ZERO, "unclassified_account_count": unclassified},
            "metadata": {"canonical_source": "POSTED_JOURNAL_LINES", "earnings_period_start": date(as_of_date.year, 1, 1), "closing_journal_detection": "NOT_AVAILABLE", "earnings_reconciled": True},
        }

    def profit_and_loss(
        self, *, date_from: date, date_to: date, comparative_date_from: date | None = None,
        comparative_date_to: date | None = None, account_id=None, parent_account_id=None,
        location_id=None, department_id=None, business_unit_id=None, include_zero_balance=False,
        include_inactive=False, detail_level="DETAIL",
    ) -> dict:
        if date_from > date_to:
            raise ValueError("date_from must be on or before date_to")
        if bool(comparative_date_from) != bool(comparative_date_to):
            raise ValueError("both comparative dates are required")
        if comparative_date_from and comparative_date_from > comparative_date_to:
            raise ValueError("comparative_date_from must be on or before comparative_date_to")
        filters = self._filters(account_id, parent_account_id, include_inactive, location_id, department_id, business_unit_id)
        rows = self._trial(date_from, date_to, **filters)
        comp_rows = self._trial(comparative_date_from, comparative_date_to, **filters) if comparative_date_from else []
        comparisons = {row["account_id"]: row for row in comp_rows}
        group_codes = ("OPERATING_REVENUE", "OTHER_REVENUE", "UNCLASSIFIED_REVENUE", "COST_OF_REVENUE", "OPERATING_EXPENSE", "OTHER_EXPENSE", "UNCLASSIFIED_EXPENSE")
        groups = {code: [] for code in group_codes};unclassified = 0
        for row in rows:
            if row["account_type"] not in {"REVENUE", "EXPENSE"}:
                continue
            amount = self._period_amount(row)
            comp = self._period_amount(comparisons[row["account_id"]]) if row["account_id"] in comparisons else ZERO
            comparative = comp if comparative_date_from else None
            if not include_zero_balance and amount == ZERO and (comparative is None or comparative == ZERO):
                continue
            configured = row.get("financial_statement_group")
            allowed = {"OPERATING_REVENUE", "OTHER_REVENUE"} if row["account_type"] == "REVENUE" else {"COST_OF_REVENUE", "OPERATING_EXPENSE", "OTHER_EXPENSE"}
            group = configured if configured in allowed else f"UNCLASSIFIED_{row['account_type']}"
            if group.startswith("UNCLASSIFIED"):
                unclassified += 1
            variance, percentage = self._variance(amount, comparative)
            groups[group].append({**row, "current_amount": amount, "comparative_amount": comparative, "variance_amount": variance, "variance_percentage": percentage})
        sections = []
        for code, label, codes in (("REVENUE", "Revenue", ("OPERATING_REVENUE", "OTHER_REVENUE", "UNCLASSIFIED_REVENUE")), ("COST_OF_REVENUE", "Cost of Revenue", ("COST_OF_REVENUE",)), ("EXPENSES", "Expenses", ("OPERATING_EXPENSE", "OTHER_EXPENSE", "UNCLASSIFIED_EXPENSE"))):
            section_groups=[]
            for group_code in codes:
                accounts=sorted(groups[group_code],key=lambda row:row["account_code"]);total=sum((row["current_amount"] for row in accounts),ZERO);comparative_total=sum((row["comparative_amount"] or ZERO for row in accounts),ZERO) if comparative_date_from else None;variance,percentage=self._variance(total,comparative_total)
                if accounts or include_zero_balance:section_groups.append({"code":group_code,"label":GROUP_LABELS[group_code],"accounts":accounts if detail_level=="DETAIL" else [],"total":total,"comparative_total":comparative_total,"variance_amount":variance,"variance_percentage":percentage})
            section_total=sum((g["total"] for g in section_groups),ZERO);comparative_total=sum((g["comparative_total"] or ZERO for g in section_groups),ZERO) if comparative_date_from else None;variance,percentage=self._variance(section_total,comparative_total)
            sections.append({"code":code,"label":label,"groups":section_groups,"total":section_total,"comparative_total":comparative_total,"variance_amount":variance,"variance_percentage":percentage})
        totals={code:sum((row["current_amount"] for row in groups[code]),ZERO) for code in group_codes}
        operating_revenue=totals["OPERATING_REVENUE"]
        cost=totals["COST_OF_REVENUE"];gross=operating_revenue-cost;operating_expenses=totals["OPERATING_EXPENSE"];operating_profit=gross-operating_expenses;other_revenue=totals["OTHER_REVENUE"];other_expenses=totals["OTHER_EXPENSE"];unclassified_net=totals["UNCLASSIFIED_REVENUE"]-totals["UNCLASSIFIED_EXPENSE"];net=operating_profit+other_revenue-other_expenses+unclassified_net
        return {"date_from":date_from,"date_to":date_to,"comparative_date_from":comparative_date_from,"comparative_date_to":comparative_date_to,"detail_level":detail_level,"sections":sections,"summary":{"total_revenue":operating_revenue+other_revenue+totals["UNCLASSIFIED_REVENUE"],"cost_of_revenue":cost,"gross_profit":gross,"operating_expenses":operating_expenses,"operating_profit":operating_profit,"other_revenue":other_revenue,"other_expenses":other_expenses,"unclassified_net":unclassified_net,"net_profit_before_tax":net,"tax_expense":ZERO,"net_profit_after_tax":net,"unclassified_account_count":unclassified},"metadata":{"canonical_source":"POSTED_JOURNAL_LINES","reconciles_to_period_trial_balance":True}}
