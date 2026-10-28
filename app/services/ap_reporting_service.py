from __future__ import annotations
from app.services.document_accounting import accounted_invoice_filter, accounted_payment_filter, accounted_adjustment_filter

from datetime import date
from decimal import Decimal
from math import ceil

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.models.payment import Payment, PaymentAllocation
from app.models.supplier import Supplier
from app.models.supplier_adjustment import SupplierAdjustment
from app.models.supplier_invoice import SupplierInvoice
from app.services.organization_access import effective_business_unit

ZERO = Decimal("0.00")
BUCKETS = ("current", "1_30", "31_60", "61_90", "over_90")


def _status(total: Decimal, paid: Decimal, adjustments: Decimal, outstanding: Decimal) -> str:
    if total > ZERO and outstanding <= ZERO:
        return "PAID"
    if paid > ZERO or adjustments > ZERO:
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


class APReportingService:
    """Read-only Accounts Payable reporting built on posted supplier invoices and payments."""

    def __init__(self, db: Session):
        self.db = db

    def _invoice_query(
        self,
        *,
        supplier_id: int | None = None,
        business_unit_id: int | None = None,
        location_id: int | None = None,
        department_id: int | None = None,
        search: str | None = None,
    ):
        query = (
            self.db.query(SupplierInvoice)
            .options(joinedload(SupplierInvoice.supplier))
            .filter(accounted_invoice_filter())
        )
        if supplier_id:
            query = query.filter(SupplierInvoice.supplier_id == supplier_id)
        if business_unit_id:
            query = query.filter(effective_business_unit(SupplierInvoice.business_unit_id, SupplierInvoice.location_id) == business_unit_id)
        if location_id:
            query = query.filter(SupplierInvoice.location_id == location_id)
        if department_id:
            query = query.filter(SupplierInvoice.department_id == department_id)
        if search:
            token = f"%{search.strip()}%"
            query = query.join(Supplier, Supplier.id == SupplierInvoice.supplier_id).filter(
                or_(
                    SupplierInvoice.internal_invoice_number.ilike(token),
                    SupplierInvoice.supplier_invoice_number.ilike(token),
                    Supplier.code.ilike(token),
                    Supplier.name.ilike(token),
                )
            )
        return query

    def _posted_payments(self, invoice_ids: list[int]) -> dict[int, dict]:
        if not invoice_ids:
            return {}
        rows = (
            self.db.query(
                PaymentAllocation.supplier_invoice_id,
                func.coalesce(func.sum(PaymentAllocation.allocated_amount), 0),
                func.max(Payment.payment_date),
            )
            .join(Payment, Payment.id == PaymentAllocation.payment_id)
            .filter(
                accounted_payment_filter(),
                PaymentAllocation.supplier_invoice_id.in_(invoice_ids),
            )
            .group_by(PaymentAllocation.supplier_invoice_id)
            .all()
        )
        return {
            int(invoice_id): {
                "paid_amount": Decimal(paid_amount or 0),
                "last_payment_date": last_payment_date,
            }
            for invoice_id, paid_amount, last_payment_date in rows
        }

    def _posted_adjustments(self, invoice_ids: list[int]) -> dict[int, Decimal]:
        if not invoice_ids:
            return {}
        rows = (
            self.db.query(
                SupplierAdjustment.supplier_invoice_id,
                func.coalesce(func.sum(SupplierAdjustment.amount), 0),
            )
            .filter(
                accounted_adjustment_filter(),
                SupplierAdjustment.supplier_invoice_id.in_(invoice_ids),
            )
            .group_by(SupplierAdjustment.supplier_invoice_id)
            .all()
        )
        return {
            int(invoice_id): Decimal(amount or 0)
            for invoice_id, amount in rows
        }

    def _rows(self, **filters) -> list[dict]:
        invoices = self._invoice_query(**filters).order_by(SupplierInvoice.id.desc()).all()
        invoice_ids = [row.id for row in invoices]
        payments = self._posted_payments(invoice_ids)
        adjustments_by_invoice = self._posted_adjustments(invoice_ids)
        today = date.today()
        result = []
        for invoice in invoices:
            total = Decimal(invoice.total_amount or 0)
            payment = payments.get(invoice.id, {})
            paid = Decimal(payment.get("paid_amount", 0) or 0)
            adjustments = adjustments_by_invoice.get(invoice.id, ZERO)
            outstanding = max(ZERO, total - paid - adjustments)
            days = max((today - invoice.due_date).days, 0) if invoice.due_date else 0
            result.append({
                "invoice_id": invoice.id,
                "invoice_number": invoice.internal_invoice_number,
                "supplier_invoice_number": invoice.supplier_invoice_number,
                "supplier_id": invoice.supplier_id,
                "supplier_code": invoice.supplier.code if invoice.supplier else None,
                "supplier_name": invoice.supplier.name if invoice.supplier else None,
                "invoice_date": invoice.invoice_date,
                "due_date": invoice.due_date,
                "gross_amount": total,
                "paid_amount": paid,
                "adjustment_amount": adjustments,
                "outstanding_amount": outstanding,
                "status": _status(total, paid, adjustments, outstanding),
                "last_payment_date": payment.get("last_payment_date"),
                "days_overdue": days,
                "aging_bucket": _bucket(days if invoice.due_date and invoice.due_date < today else 0),
                "business_unit_id": invoice.business_unit_id,
                "location_id": invoice.location_id,
                "department_id": invoice.department_id,
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
        supplier_map: dict[int, dict] = {}
        for row in rows:
            supplier = supplier_map.setdefault(row["supplier_id"], {
                "supplier_id": row["supplier_id"],
                "supplier_code": row["supplier_code"],
                "supplier_name": row["supplier_name"],
                "gross_amount": ZERO,
                "paid_amount": ZERO,
                "adjustment_amount": ZERO,
                "outstanding_amount": ZERO,
                "invoice_count": 0,
                "open_invoice_count": 0,
            })
            supplier["gross_amount"] += row["gross_amount"]
            supplier["paid_amount"] += row["paid_amount"]
            supplier["adjustment_amount"] += row["adjustment_amount"]
            supplier["outstanding_amount"] += row["outstanding_amount"]
            supplier["invoice_count"] += 1
            if row["outstanding_amount"] > ZERO:
                supplier["open_invoice_count"] += 1

        supplier_rows = list(supplier_map.values())
        for row in supplier_rows:
            row["status"] = _status(
                row["gross_amount"], row["paid_amount"], row["adjustment_amount"], row["outstanding_amount"]
            )
        supplier_rows.sort(key=lambda row: (-row["outstanding_amount"], (row["supplier_name"] or "").upper()))

        gross = sum((row["gross_amount"] for row in rows), ZERO)
        paid = sum((row["paid_amount"] for row in rows), ZERO)
        adjustments = sum((row["adjustment_amount"] for row in rows), ZERO)
        outstanding = sum((row["outstanding_amount"] for row in rows), ZERO)

        status_counts = {"PAID": 0, "PARTIALLY_PAID": 0, "UNPAID": 0}
        for row in supplier_rows:
            status_counts[row["status"]] += 1

        paged = self._paginate(supplier_rows, page, page_size)
        return {
            "metrics": {
                "gross_payables": gross,
                "total_payments": paid,
                "total_adjustments": adjustments,
                "outstanding_payables": outstanding,
                "supplier_count": len(supplier_rows),
                "invoice_count": len(rows),
            },
            "status_counts": status_counts,
            **paged,
        }

    def detail(self, *, page: int = 1, page_size: int = 20, status: str | None = None, **filters) -> dict:
        rows = self._rows(**filters)
        if status:
            rows = [row for row in rows if row["status"] == status.upper()]
        return self._paginate(rows, page, page_size)

    def aging(self, *, page: int = 1, page_size: int = 20, **filters) -> dict:
        rows = [row for row in self._rows(**filters) if row["outstanding_amount"] > ZERO]
        buckets = {key: {"amount": ZERO, "invoice_count": 0, "supplier_ids": set()} for key in BUCKETS}
        supplier_map: dict[int, dict] = {}
        for row in rows:
            bucket = buckets[row["aging_bucket"]]
            bucket["amount"] += row["outstanding_amount"]
            bucket["invoice_count"] += 1
            bucket["supplier_ids"].add(row["supplier_id"])

            supplier = supplier_map.setdefault(row["supplier_id"], {
                "supplier_id": row["supplier_id"],
                "supplier_code": row["supplier_code"],
                "supplier_name": row["supplier_name"],
                **{key: ZERO for key in BUCKETS},
                "outstanding_amount": ZERO,
            })
            supplier[row["aging_bucket"]] += row["outstanding_amount"]
            supplier["outstanding_amount"] += row["outstanding_amount"]

        bucket_output = {
            key: {
                "amount": value["amount"],
                "invoice_count": value["invoice_count"],
                "supplier_count": len(value["supplier_ids"]),
            }
            for key, value in buckets.items()
        }
        supplier_rows = sorted(
            supplier_map.values(),
            key=lambda row: (-row["outstanding_amount"], (row["supplier_name"] or "").upper()),
        )
        return {
            "as_of_date": date.today(),
            "total_outstanding": sum((row["outstanding_amount"] for row in rows), ZERO),
            "buckets": bucket_output,
            **self._paginate(supplier_rows, page, page_size),
        }
