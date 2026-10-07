"""Management presentation from posted activity, without balancing writes."""
from calendar import monthrange
from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import func

from app.models.chart_of_account import ChartOfAccount
from app.models.department import Department
from app.models.location_department import LocationDepartment
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.services.financial_reporting_service import FinancialReportingService

ZERO = Decimal("0")


def activity_rows(db, end, scope):
    department = func.coalesce(JournalLine.department_id, JournalEntry.department_id)
    month = func.extract("month", JournalEntry.posting_date)
    query = db.query(month, department, ChartOfAccount.id, ChartOfAccount.account_name,
        ChartOfAccount.account_type, ChartOfAccount.financial_statement_group,
        func.sum(JournalLine.debit - JournalLine.credit)).join(
        JournalEntry, JournalEntry.id == JournalLine.journal_entry_id).join(
        ChartOfAccount, ChartOfAccount.id == JournalLine.account_id).filter(
        JournalEntry.status == "POSTED",
        JournalEntry.posting_date.between(date(end.year, 1, 1), end),
        ChartOfAccount.account_type.in_(("REVENUE", "INCOME", "EXPENSE")),
        func.coalesce(JournalEntry.reference_type, "").notin_(
            ("OPENING_BALANCE", "OPENING_BALANCE_ADJUSTMENT", "PERIOD_CLOSE", "YEAR_END")))
    for name, value in scope.items():
        if value is not None:
            query = query.filter(func.coalesce(getattr(JournalLine, name), getattr(JournalEntry, name)) == value)
    return query.group_by(month, department, ChartOfAccount.id, ChartOfAccount.account_name,
        ChartOfAccount.account_type, ChartOfAccount.financial_statement_group).all()


def performance(rows):
    revenue = cogs = operating = other = ZERO
    for _, _, _, _, kind, group, amount in rows:
        amount = Decimal(amount or 0)
        if kind in ("REVENUE", "INCOME"):
            revenue -= amount
        elif group == "COST_OF_REVENUE":
            cogs += amount
        elif group == "OPERATING_EXPENSE":
            operating += amount
        else:
            other += amount
    goi = revenue - cogs
    gop = goi - operating
    nop = gop - other
    return dict(revenue=revenue, cogs=cogs, operating_expenses=operating, other_expenses=other,
        goi=goi, gop=gop, nop=nop,
        gop_margin=gop / revenue * 100 if revenue else None,
        nop_margin=nop / revenue * 100 if revenue else None)


def departments(db, rows, month, scope=None):
    names = {d.id: d.name for d in db.query(Department).all()}
    groups = defaultdict(list)
    scope = scope or {}
    configured = db.query(Department).filter(Department.is_active.is_(True))
    if scope.get("location_id") is not None:
        configured = configured.join(LocationDepartment).filter(LocationDepartment.location_id == scope["location_id"])
    if scope.get("business_unit_id") is not None:
        configured = configured.filter(Department.business_unit_id == scope["business_unit_id"])
    if scope.get("department_id") is not None:
        configured = configured.filter(Department.id == scope["department_id"])
    for department in configured:
        groups[department.id] = []
    for row in rows:
        groups[row[1]].append(row)
    return [dict(department_id=key, department_name=names.get(key, "Unassigned department"),
        MTD=performance([r for r in values if int(r[0]) == month]), YTD=performance(values))
        for key, values in sorted(groups.items(), key=lambda item: names.get(item[0], "Unassigned department"))]


def build_dashboard(db, *, year, month, location_id=None, business_unit_id=None, department_id=None):
    end = date(year, month, monthrange(year, month)[1])
    scope = dict(location_id=location_id, business_unit_id=business_unit_id, department_id=department_id)
    rows = activity_rows(db, end, scope)
    selected = [r for r in rows if int(r[0]) == month]
    accounts = defaultdict(lambda: ZERO)
    for _, _, aid, name, kind, _, amount in selected:
        accounts[(aid, name, kind)] += -Decimal(amount) if kind in ("REVENUE", "INCOME") else Decimal(amount)
    ranking = lambda kinds: [dict(account_id=aid, account_name=name, amount=amount)
        for (aid, name, kind), amount in sorted(accounts.items(), key=lambda item: item[1], reverse=True)
        if kind in kinds and amount != ZERO][:8]
    position = FinancialReportingService(db).build(report_type="BALANCE_SHEET", as_of_date=end, detail=True, **scope)
    debit_assets = {a.id for a in db.query(ChartOfAccount).filter_by(account_type="ASSET", normal_balance="DEBIT")}
    totals = {key: value["YTD"]["current"] for key, value in position["section_totals"].items()}
    return dict(as_of_date=end, scope=scope, scope_labels=position["scope_labels"],
        MTD=performance(selected), YTD=performance(rows),
        monthly=[dict(month=m, **performance([r for r in rows if int(r[0]) == m])) for m in range(1, month + 1)],
        departments=departments(db, rows, month, scope), top_revenue=ranking(("REVENUE", "INCOME")),
        top_cost=ranking(("EXPENSE",)), position=totals,
        balance_gap=totals["ASSETS"] - totals["LIABILITIES"] - totals["EQUITY"],
        negative_assets=[r for r in position["rows"] if r["section"] == "ASSETS" and set(r["account_ids"]) & debit_assets and r["periods"]["YTD"]["current"] < ZERO],
        definitions={"goi": "Revenue less cost of revenue", "gop": "GOI less operating expenses",
            "nop": "Revenue less all expenses; includes unclassified expenses"})
