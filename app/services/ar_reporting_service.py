from __future__ import annotations

from datetime import date
from decimal import Decimal
from math import ceil

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.models.account_receivable import AccountReceivable
from app.models.customer import Customer

ZERO = Decimal("0.00")
BUCKETS = ("current", "1_30", "31_60", "61_90", "over_90")


def _status(total: Decimal, received: Decimal, outstanding: Decimal) -> str:
    if total > ZERO and outstanding <= ZERO:
        return "PAID"
    if received > ZERO:
        return "PARTIALLY_PAID"
    return "UNPAID"


def _bucket(days_overdue: int) -> str:
    if days_overdue <= 0:
        return "current"
    if days_overdue <= 30:
        return "1_30"
    if days_overdue <= 60:
        return "31_60"
    if days_overdue <= 90:
        return "61_90"
    return "over_90"


class ARReportingService:
    """Read-only reporting over the canonical AccountReceivable balance."""

    def __init__(self, db: Session):
        self.db = db

    def _query(
        self,
        *,
        customer_id: int | None = None,
        search: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ):
        query = (
            self.db.query(AccountReceivable)
            .options(joinedload(AccountReceivable.customer))
        )
        if customer_id:
            query = query.filter(AccountReceivable.customer_id == customer_id)
        if search:
            token = f"%{search.strip()}%"
            query = query.join(Customer, Customer.id == AccountReceivable.customer_id).filter(
                or_(
                    AccountReceivable.invoice_number.ilike(token),
                    Customer.customer_code.ilike(token),
                    Customer.customer_name.ilike(token),
                )
            )
        if date_from:
            query = query.filter(AccountReceivable.invoice_date >= date_from)
        if date_to:
            query = query.filter(AccountReceivable.invoice_date <= date_to)
        return query

    def _rows(self, **filters) -> list[dict]:
        today = date.today()
        result = []
        for invoice in self._query(**filters).order_by(AccountReceivable.id.desc()).all():
            total = Decimal(invoice.amount or 0)
            received = max(ZERO, Decimal(invoice.received_amount or 0))
            outstanding = max(ZERO, Decimal(invoice.outstanding_amount or 0))
            days = max((today - invoice.due_date).days, 0) if invoice.due_date else 0
            customer = invoice.customer
            result.append({
                "invoice_id": invoice.id,
                "invoice_number": invoice.invoice_number,
                "customer_id": invoice.customer_id,
                "customer_code": customer.customer_code if customer else None,
                "customer_name": customer.customer_name if customer else None,
                "invoice_date": invoice.invoice_date,
                "due_date": invoice.due_date,
                "gross_amount": total,
                "received_amount": received,
                "outstanding_amount": outstanding,
                "status": _status(total, received, outstanding),
                "days_overdue": days,
                "aging_bucket": _bucket(days if invoice.due_date and invoice.due_date < today else 0),
            })
        return result

    @staticmethod
    def _paginate(rows: list[dict], page: int, page_size: int) -> dict:
        total_items = len(rows)
        total_pages = ceil(total_items / page_size) if total_items else 0
        start = (page - 1) * page_size
        return {
            "items": rows[start:start + page_size],
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_previous": page > 1,
        }

    def summary(self, *, page: int = 1, page_size: int = 20, **filters) -> dict:
        rows = self._rows(**filters)
        customer_map: dict[int, dict] = {}
        for row in rows:
            customer = customer_map.setdefault(row["customer_id"], {
                "customer_id": row["customer_id"],
                "customer_code": row["customer_code"],
                "customer_name": row["customer_name"],
                "gross_amount": ZERO,
                "received_amount": ZERO,
                "outstanding_amount": ZERO,
                "invoice_count": 0,
                "open_invoice_count": 0,
                "overdue_invoice_count": 0,
            })
            customer["gross_amount"] += row["gross_amount"]
            customer["received_amount"] += row["received_amount"]
            customer["outstanding_amount"] += row["outstanding_amount"]
            customer["invoice_count"] += 1
            if row["outstanding_amount"] > ZERO:
                customer["open_invoice_count"] += 1
                if row["days_overdue"] > 0:
                    customer["overdue_invoice_count"] += 1

        customer_rows = list(customer_map.values())
        for row in customer_rows:
            row["status"] = _status(
                row["gross_amount"], row["received_amount"], row["outstanding_amount"]
            )
        customer_rows.sort(
            key=lambda row: (-row["outstanding_amount"], (row["customer_name"] or "").upper())
        )
        gross = sum((row["gross_amount"] for row in rows), ZERO)
        received = sum((row["received_amount"] for row in rows), ZERO)
        outstanding = sum((row["outstanding_amount"] for row in rows), ZERO)
        overdue = sum(
            (row["outstanding_amount"] for row in rows if row["days_overdue"] > 0),
            ZERO,
        )
        return {
            "metrics": {
                "gross_receivables": gross,
                "total_receipts": received,
                "outstanding_receivables": outstanding,
                "overdue_receivables": overdue,
                "customer_count": len(customer_rows),
                "invoice_count": len(rows),
            },
            **self._paginate(customer_rows, page, page_size),
        }

    def detail(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        **filters,
    ) -> dict:
        rows = self._rows(**filters)
        if status:
            rows = [row for row in rows if row["status"] == status.upper()]
        return self._paginate(rows, page, page_size)

    def aging(self, *, page: int = 1, page_size: int = 20, **filters) -> dict:
        rows = [row for row in self._rows(**filters) if row["outstanding_amount"] > ZERO]
        buckets = {
            key: {"amount": ZERO, "invoice_count": 0, "customer_ids": set()}
            for key in BUCKETS
        }
        customer_map: dict[int, dict] = {}
        for row in rows:
            bucket = buckets[row["aging_bucket"]]
            bucket["amount"] += row["outstanding_amount"]
            bucket["invoice_count"] += 1
            bucket["customer_ids"].add(row["customer_id"])

            customer = customer_map.setdefault(row["customer_id"], {
                "customer_id": row["customer_id"],
                "customer_code": row["customer_code"],
                "customer_name": row["customer_name"],
                **{key: ZERO for key in BUCKETS},
                "outstanding_amount": ZERO,
            })
            customer[row["aging_bucket"]] += row["outstanding_amount"]
            customer["outstanding_amount"] += row["outstanding_amount"]

        customer_rows = sorted(
            customer_map.values(),
            key=lambda row: (-row["outstanding_amount"], (row["customer_name"] or "").upper()),
        )
        return {
            "as_of_date": date.today(),
            "total_outstanding": sum((row["outstanding_amount"] for row in rows), ZERO),
            "buckets": {
                key: {
                    "amount": value["amount"],
                    "invoice_count": value["invoice_count"],
                    "customer_count": len(value["customer_ids"]),
                }
                for key, value in buckets.items()
            },
            **self._paginate(customer_rows, page, page_size),
        }
