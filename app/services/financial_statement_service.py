from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session
from app.models.accounting_setting import AccountingSetting
from app.models.chart_of_account import ChartOfAccount

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

    def _period_rows(self, date_from: date, date_to: date, **filters) -> list[dict]:
        rows = self._trial(date(date_to.year, 1, 1), date_to, **filters)
        activity = self.trial._activity(date_from=date_from, date_to=date_to, exclude_closing=True,
            location_id=filters.get("location_id"), department_id=filters.get("department_id"),
            business_unit_id=filters.get("business_unit_id"))
        for row in rows:
            row["period_debit"], row["period_credit"] = activity.get(row["account_id"], (ZERO, ZERO))
        return rows

    @staticmethod
    def _variance(current: Decimal, comparative: Decimal | None) -> tuple[Decimal | None, Decimal | None]:
        if comparative is None:
            return None, None
        variance = current - comparative
        percentage = variance / abs(comparative) * Decimal("100") if comparative != ZERO else None
        return variance, percentage

    @staticmethod
    def _net(row: dict) -> Decimal:
        """Return the canonical, normal-balance-adjusted closing balance."""
        return Decimal(row.get("closing_balance") or ZERO)

    @staticmethod
    def _period_amount(row: dict) -> Decimal:
        return row["period_credit"] - row["period_debit"] if row["account_type"] in {"REVENUE", "INCOME"} else row["period_debit"] - row["period_credit"]

    def _filters(self, account_id, parent_account_id, include_inactive, location_id, department_id, business_unit_id=None):
        return {
            "account_id": account_id, "parent_account_id": parent_account_id,
            "include_inactive": include_inactive, "location_id": location_id,
            "department_id": department_id,
            "business_unit_id": business_unit_id,
        }

    def earnings(self, as_of_date: date, **filters) -> Decimal:
        rows = self._trial(date(as_of_date.year, 1, 1), as_of_date, **filters)
        revenue = sum((self._period_amount(row) for row in rows if row["account_type"] in {"REVENUE", "INCOME"}), ZERO)
        expense = sum((self._period_amount(row) for row in rows if row["account_type"] == "EXPENSE"), ZERO)
        return revenue - expense

    def balance_sheet(
        self, *, as_of_date: date, comparative_date: date | None = None,
        fiscal_year: int | None = None,
        account_id=None, parent_account_id=None, location_id=None, department_id=None, business_unit_id=None,
        include_zero_balance=False, include_inactive=False, detail_level="DETAIL",
    ) -> dict:
        """Yearly balance sheet (Neraca) with carried balances as of the as-of date.

        Reflects a running, carried-forward balance: each balance-sheet account shows its
        current balance as of `as_of_date` (which includes balances carried from prior periods).
        Actual equity accounts retain their identifiers. Residual current-year
        earnings are displayed with the configured closing equity account and
        traced separately from saved opening balances and posted movements.
        """
        if fiscal_year is not None:
            as_of_date = as_of_date or date(fiscal_year, 12, 31)
        if as_of_date is None:
            raise ValueError("as_of_date (or fiscal_year) is required")
        fiscal_year = fiscal_year or as_of_date.year
        year_start = date(fiscal_year, 1, 1)
        year_end = date(fiscal_year, 12, 31)

        filters = self._filters(account_id, parent_account_id, include_inactive, location_id, department_id, business_unit_id)
        rows = self._trial(year_start, as_of_date, **filters)
        groups = {code: [] for values in BALANCE_GROUPS.values() for code in values}
        unclassified = 0
        for row in rows:
            account_type = row["account_type"]
            if account_type not in BALANCE_GROUPS:
                continue
            expected = "DEBIT" if account_type == "ASSET" else "CREDIT"
            sign = Decimal(1) if row["normal_balance"] == expected else Decimal(-1)
            opening = Decimal(row.get("opening_balance") or ZERO) * sign
            closing = Decimal(row.get("closing_balance") or ZERO) * sign
            if not include_zero_balance and opening == ZERO and closing == ZERO:
                continue
            configured = row.get("financial_statement_group")
            allowed = set(BALANCE_GROUPS[account_type][:-1] if account_type != "EQUITY" else ("EQUITY",))
            group = configured if configured in allowed else BALANCE_GROUPS[account_type][-1]
            if group.startswith("UNCLASSIFIED"):
                unclassified += 1
            groups[group].append({**row, "opening_amount": opening, "closing_amount": closing})

        current_earnings = self.earnings(as_of_date, **filters)
        opening_earnings = ZERO
        setting = self.db.query(AccountingSetting).filter_by(setting_key="CURRENT_YEAR_EARNINGS_ACCOUNT").first()
        earnings_account = self.db.get(ChartOfAccount, setting.account_id) if setting and setting.account_id else None
        if not earnings_account or earnings_account.account_type != "EQUITY" or not earnings_account.is_posting or earnings_account.normal_balance != "CREDIT":
            earnings_account = None
        equity_rows = groups["EQUITY"] + groups["UNCLASSIFIED_EQUITY"]
        target = next((row for row in equity_rows if earnings_account and row["account_id"] == earnings_account.id), None)
        # Only aggregate for presentation. Saved opening and journal evidence
        # remain separate; closing entries already included in the ledger reduce
        # the residual P&L, so they must never be counted a second time.
        if target is None and earnings_account and not account_id and not parent_account_id:
            target = {"account_id": earnings_account.id, "account_code": earnings_account.account_number,
                      "account_name": earnings_account.account_name, "account_type": "EQUITY",
                      "parent_account_id": earnings_account.parent_account_id,
                      "financial_statement_group": "EQUITY", "opening_amount": ZERO, "closing_amount": ZERO}
            if current_earnings != ZERO or include_zero_balance: groups["EQUITY"].append(target)
        equity_evidence = {"account_id": target["account_id"] if target else None,
                           "account_name": target["account_name"] if target else None,
                           "opening_balance": target["opening_amount"] if target else ZERO,
                           "posted_movement": target["closing_amount"] - target["opening_amount"] if target else ZERO,
                           "unclosed_profit_loss": current_earnings}
        if target is not None:
            target["closing_amount"] += current_earnings
            target["includes_unclosed_earnings"] = True
        elif current_earnings != ZERO or include_zero_balance:
            groups["EQUITY"].append({
                "account_id": None, "account_code": "", "account_name": "Laba/Rugi Tahun Berjalan (Belum Ditutup)",
                "account_type": "EQUITY", "parent_account_id": None,
                "financial_statement_group": "CURRENT_PERIOD_EARNINGS",
                "opening_amount": ZERO, "closing_amount": current_earnings,
                "is_synthetic": True, "includes_unclosed_earnings": True,
            })
        equity_evidence["displayed_balance"] = equity_evidence["opening_balance"] + equity_evidence["posted_movement"] + current_earnings
        section_specs = [("ASSETS", "Assets", "ASSET"), ("LIABILITIES", "Liabilities", "LIABILITY"), ("EQUITY", "Equity", "EQUITY")]
        sections = []
        for section_code, section_label, account_type in section_specs:
            section_groups = []
            for group_code in BALANCE_GROUPS[account_type]:
                accounts = sorted(groups[group_code], key=lambda row: row["account_code"])
                opening_total = sum((row["opening_amount"] for row in accounts), ZERO)
                closing_total = sum((row["closing_amount"] for row in accounts), ZERO)
                if accounts or include_zero_balance:
                    section_groups.append({"code": group_code, "label": GROUP_LABELS[group_code], "accounts": accounts if detail_level == "DETAIL" else [], "opening_total": opening_total, "closing_total": closing_total})
            if account_type == "EQUITY" and detail_level == "SUMMARY":
                target = next((group for group in section_groups if group["code"] == "EQUITY"), None)
                if target:
                    target["accounts"] = []
            opening_total = sum((group["opening_total"] for group in section_groups), ZERO)
            closing_total = sum((group["closing_total"] for group in section_groups), ZERO)
            sections.append({"code": section_code, "label": section_label, "groups": section_groups, "opening_total": opening_total, "closing_total": closing_total})
        totals = {section["code"]: section["closing_total"] for section in sections}
        opening_totals = {section["code"]: section["opening_total"] for section in sections}
        liabilities_equity = totals["LIABILITIES"] + totals["EQUITY"]
        opening_liabilities_equity = opening_totals["LIABILITIES"] + opening_totals["EQUITY"]
        difference = totals["ASSETS"] - liabilities_equity
        opening_difference = opening_totals["ASSETS"] - opening_liabilities_equity
        return {
            "as_of_date": as_of_date, "comparative_date": None, "detail_level": detail_level,
            "fiscal_year": fiscal_year, "year_start": year_start, "year_end": year_end,
            "sections": sections,
            "summary": {
                "opening_total_assets": opening_totals["ASSETS"], "opening_total_liabilities": opening_totals["LIABILITIES"],
                "opening_total_equity": opening_totals["EQUITY"], "opening_current_period_earnings": opening_earnings,
                "opening_total_liabilities_and_equity": opening_liabilities_equity, "opening_difference": opening_difference,
                "opening_is_balanced": opening_difference == ZERO,
                "total_assets": totals["ASSETS"], "total_liabilities": totals["LIABILITIES"], "total_equity": totals["EQUITY"],
                "current_period_earnings": current_earnings, "total_liabilities_and_equity": liabilities_equity,
                "earnings_reconciliation": equity_evidence,
                "difference": difference, "is_balanced": difference == ZERO, "unclassified_account_count": unclassified,
            },
            "metadata": {"canonical_source": "OPENING_BALANCES_AND_POSTED_JOURNAL_LINES", "earnings_period_start": date(as_of_date.year, 1, 1), "closing_journal_detection": "PERIOD_CLOSE_AND_YEAR_END", "earnings_reconciled": True, "is_yearly": True, "year_start": year_start, "year_end": year_end},
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
        rows = self._period_rows(date_from, date_to, **filters)
        comp_rows = self._period_rows(comparative_date_from, comparative_date_to, **filters) if comparative_date_from else []
        comparisons = {row["account_id"]: row for row in comp_rows}
        group_codes = ("OPERATING_REVENUE", "OTHER_REVENUE", "UNCLASSIFIED_REVENUE", "COST_OF_REVENUE", "OPERATING_EXPENSE", "OTHER_EXPENSE", "UNCLASSIFIED_EXPENSE")
        groups = {code: [] for code in group_codes};unclassified = 0
        for row in rows:
            if row["account_type"] not in {"REVENUE", "INCOME", "EXPENSE"}:
                continue
            amount = self._period_amount(row)
            comp = self._period_amount(comparisons[row["account_id"]]) if row["account_id"] in comparisons else ZERO
            comparative = comp if comparative_date_from else None
            if not include_zero_balance and amount == ZERO and (comparative is None or comparative == ZERO):
                continue
            configured = row.get("financial_statement_group")
            allowed = {"OPERATING_REVENUE", "OTHER_REVENUE"} if row["account_type"] in {"REVENUE", "INCOME"} else {"COST_OF_REVENUE", "OPERATING_EXPENSE", "OTHER_EXPENSE"}
            group = configured if configured in allowed else ("UNCLASSIFIED_REVENUE" if row["account_type"] in {"REVENUE", "INCOME"} else "UNCLASSIFIED_EXPENSE")
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
        return {"date_from":date_from,"date_to":date_to,"comparative_date_from":comparative_date_from,"comparative_date_to":comparative_date_to,"detail_level":detail_level,"sections":sections,"summary":{"total_revenue":operating_revenue+other_revenue+totals["UNCLASSIFIED_REVENUE"],"cost_of_revenue":cost,"gross_profit":gross,"operating_expenses":operating_expenses,"operating_profit":operating_profit,"other_revenue":other_revenue,"other_expenses":other_expenses,"unclassified_net":unclassified_net,"net_profit_before_tax":net,"tax_expense":ZERO,"net_profit_after_tax":net,"unclassified_account_count":unclassified},"metadata":{"canonical_source":"POSTED_JOURNAL_LINES","operating_movement_before_closing":True}}
