from app.services.organization_access import effective_business_unit
from datetime import date
from decimal import Decimal
from math import ceil

from sqlalchemy import exists, func, or_
from sqlalchemy.orm import Session, joinedload

from app.models.chart_of_account import ChartOfAccount
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.services.opening_snapshot import opening_snapshot


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

    def _activity(
        self,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        before: date | None = None,
        exclude_closing: bool = False,
        location_id: int | None = None,
        department_id: int | None = None,
        business_unit_id: int | None = None,
    ) -> dict[int, tuple[Decimal, Decimal]]:
        query = (
            self.db.query(
                JournalLine.account_id,
                func.coalesce(func.sum(JournalLine.debit), 0),
                func.coalesce(func.sum(JournalLine.credit), 0),
            )
            .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
            .filter(JournalEntry.status == "POSTED")
            .filter(JournalEntry.reference_type.notin_(("OPENING_BALANCE", "OPENING_BALANCE_ADJUSTMENT")))
        )
        if exclude_closing:
            query = query.filter(JournalEntry.reference_type.notin_(("PERIOD_CLOSE", "YEAR_END")))
        if before:
            query = query.filter(JournalEntry.posting_date < before)
        if date_from:
            query = query.filter(JournalEntry.posting_date >= date_from)
        if date_to:
            query = query.filter(JournalEntry.posting_date <= date_to)
        for name, value in (("location_id", location_id), ("department_id", department_id), ("business_unit_id", business_unit_id)):
            if value is not None:
                dimension = func.coalesce(getattr(JournalLine, name), getattr(JournalEntry, name))
                if name == "business_unit_id": dimension = effective_business_unit(dimension, func.coalesce(JournalLine.location_id, JournalEntry.location_id))
                query = query.filter(dimension.is_(None) if name == "department_id" and value == 0 else dimension == value)
        return {
            account_id: (Decimal(debit), Decimal(credit))
            for account_id, debit, credit in query.group_by(JournalLine.account_id).all()
        }

    @staticmethod
    def _normal_balance_amount(normal_balance: str, debit: Decimal, credit: Decimal) -> Decimal:
        if normal_balance == "CREDIT":
            return credit - debit
        return debit - credit

    def report(
        self,
        *,
        date_from: date,
        date_to: date,
        page: int = 1,
        page_size: int = 50,
        search: str | None = None,
        account_type: str | None = None,
        account_id: int | None = None,
        parent_account_id: int | None = None,
        include_zero_balance: bool = False,
        include_inactive: bool = False,
        location_id: int | None = None,
        department_id: int | None = None,
        business_unit_id: int | None = None,
        sort_by: str = "account_code",
        sort_order: str = "asc",
        paginate: bool = True,
    ) -> dict:
        if date_from > date_to:
            raise ValueError("date_from must be on or before date_to")
        if date_from.year != date_to.year:
            raise ValueError("Trial Balance date range must be within one fiscal year")
        year_start = date(date_to.year, 1, 1)

        # Keep legacy revenue posting parents visible after code edits.
        # Other parent/header rows remain excluded from this leaf-account report.
        child = ChartOfAccount.__table__.alias("trial_balance_child")
        has_child = exists().where(child.c.parent_account_id == ChartOfAccount.id)
        accounts_query = self.db.query(ChartOfAccount).options(joinedload(ChartOfAccount.parent)).filter(
            ChartOfAccount.is_posting.is_(True),
            or_(~has_child, ChartOfAccount.account_type.in_(("REVENUE", "INCOME"))),
        )
        if not include_inactive:
            accounts_query = accounts_query.filter(ChartOfAccount.is_active.is_(True))
        if search:
            term = f"%{search.strip()}%"
            accounts_query = accounts_query.filter(
                or_(ChartOfAccount.account_number.ilike(term), ChartOfAccount.account_name.ilike(term))
            )
        if account_type:
            accounts_query = accounts_query.filter(ChartOfAccount.account_type == account_type.upper())
        if account_id:
            accounts_query = accounts_query.filter(ChartOfAccount.id == account_id)
        if parent_account_id:
            accounts_query = accounts_query.filter(ChartOfAccount.parent_account_id == parent_account_id)

        snapshot_date, snapshot = opening_snapshot(
            self.db, as_of=year_start, location_id=location_id,
            department_id=department_id, business_unit_id=business_unit_id,
        )
        # A selected year's opening is the manually entered closing of the
        # preceding year. Earlier transactions in this year remain movement.
        opening = snapshot if snapshot_date == year_start else {}
        period = self._activity(
            date_from=date_from,
            date_to=date_to,
            location_id=location_id,
            department_id=department_id,
            business_unit_id=business_unit_id,
        )

        prior = self._activity(
            date_from=year_start, before=date_from,
            location_id=location_id, department_id=department_id,
            business_unit_id=business_unit_id,
        ) if date_from > year_start else {}

        rows = []
        for account in accounts_query.all():
            opening_debit_activity, opening_credit_activity = opening.get(account.id, (ZERO, ZERO))
            prior_debit, prior_credit = prior.get(account.id, (ZERO, ZERO))
            prior_total = self._normal_balance_amount(account.normal_balance, prior_debit, prior_credit)
            period_debit, period_credit = period.get(account.id, (ZERO, ZERO))
            opening_balance = self._normal_balance_amount(
                account.normal_balance,
                opening_debit_activity,
                opening_credit_activity,
            )
            period_total = self._normal_balance_amount(
                account.normal_balance,
                period_debit,
                period_credit,
            )
            closing_balance = opening_balance + prior_total + period_total
            opening_net_debit = opening_debit_activity - opening_credit_activity
            closing_net_debit = opening_net_debit + prior_debit - prior_credit + period_debit - period_credit
            status = "ABNORMAL" if closing_balance < ZERO else "NORMAL"

            if not include_zero_balance and not any(
                (opening_debit_activity, opening_credit_activity, prior_debit, prior_credit, period_debit, period_credit)
            ):
                continue

            rows.append(
                {
                    "account_id": account.id,
                    "account_code": account.account_number,
                    "account_name": account.account_name,
                    "account_type": account.account_type,
                    "normal_balance": account.normal_balance,
                    "financial_statement_group": account.financial_statement_group,
                    "parent_account_id": account.parent_account_id,
                    "parent_account_code": account.parent.account_number if account.parent else None,
                    "parent_account_name": account.parent.account_name if account.parent else None,
                    "opening_balance": opening_balance,
                    "opening_debit": max(opening_net_debit, ZERO),
                    "opening_credit": max(-opening_net_debit, ZERO),
                    "prior_debit": prior_debit,
                    "prior_credit": prior_credit,
                    "prior_total": prior_total,
                    "period_debit": period_debit,
                    "period_credit": period_credit,
                    "period_total": period_total,
                    "closing_balance": closing_balance,
                    "closing_debit": max(closing_net_debit, ZERO),
                    "closing_credit": max(-closing_net_debit, ZERO),
                    "status": status,
                    "is_abnormal_balance": status == "ABNORMAL",
                }
            )

        key = self.SORT_FIELDS.get(sort_by, self.SORT_FIELDS["account_code"])
        rows.sort(key=key, reverse=sort_order.lower() == "desc")

        summary = {
            "opening_balance": sum((row["opening_balance"] for row in rows), ZERO),
            "prior_debit": sum((row["prior_debit"] for row in rows), ZERO),
            "prior_credit": sum((row["prior_credit"] for row in rows), ZERO),
            "prior_total": sum((row["prior_total"] for row in rows), ZERO),
            "period_debit": sum((row["period_debit"] for row in rows), ZERO),
            "period_credit": sum((row["period_credit"] for row in rows), ZERO),
            "period_total": sum((row["period_total"] for row in rows), ZERO),
            "closing_balance": sum((row["closing_balance"] for row in rows), ZERO),
        }
        summary["difference"] = summary["period_debit"] - summary["period_credit"]
        # Assess the complete posted ledger within the date/location scope. A
        # search or account filter is only a view and must not change this check.
        opening_debit = sum((debit for debit, _ in opening.values()), ZERO)
        opening_credit = sum((credit for _, credit in opening.values()), ZERO)
        period_debit_all = sum((debit for debit, _ in period.values()), ZERO)
        period_credit_all = sum((credit for _, credit in period.values()), ZERO)
        summary["opening_debit"] = opening_debit
        summary["opening_credit"] = opening_credit
        summary["opening_difference"] = opening_debit - opening_credit
        summary["closing_difference"] = (
            opening_debit + sum((d-c for d,c in prior.values()), ZERO) + period_debit_all - opening_credit - period_credit_all
        )
        summary["is_balanced"] = summary["closing_difference"] == ZERO
        summary["account_count"] = len(rows)
        summary["abnormal_balance_count"] = sum(row["is_abnormal_balance"] for row in rows)

        total = len(rows)
        items = rows[(page - 1) * page_size : page * page_size] if paginate else rows
        return {
            "items": items,
            "summary": summary,
            "opening_as_of": date(date_to.year - 1, 12, 31),
            "movement_from": date_from,
            "movement_to": date_to,
            "prior_movement_from": year_start,
            "has_prior_movement": date_from > year_start,
            "page": page,
            "page_size": page_size,
            "total_items": total,
            "total_pages": ceil(total / page_size) if total else 0,
            "has_next": paginate and page * page_size < total,
            "has_previous": paginate and page > 1,
        }
