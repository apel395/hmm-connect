"""Safe finance preparation of historical Catering AR staging rows.

Preparation is NOT accounting activation. It maps the expressly confirmed PHR
customer, user-verified terms and COA to staging records only. No AR, POS,
CustomerPayment, JournalEntry, JournalLine or GeneralLedger objects are written.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from fastapi import HTTPException

from app.models.business_unit import BusinessUnit
from app.models.chart_of_account import ChartOfAccount
from app.models.customer import Customer
from app.models.department import Department
from app.models.import_batch import ImportBatch, ImportRow
from app.models.location import Location
from app.models.location_department import LocationDepartment
from app.models.account_receivable import AccountReceivable
from app.models.sales_transaction import SalesTransaction
from app.models.journal_entry import JournalEntry
from app.services.pos_revenue import revenue_accounts
from app.services.location_access import assigned_location_id

UNRESOLVED_NOTES = (
    "Source has no legal customer identifier",
    "Source has no contractual due date",
    "AR, revenue and tax accounts need reconciliation with existing GL",
)
SOURCE = "AR_INVOICE_EXCEL"
CATERING_SITE_CODES = frozenset({"005", "006", "010", "014"})
MONEY = Decimal("0.01")


def phr_customer(db: Session) -> Customer | None:
    """PHR was confirmed for *this* workbook, not every future AR import."""
    matches = db.query(Customer).filter(
        Customer.is_active.is_(True),
        or_(
            func.upper(func.trim(Customer.customer_name)) == "PHR",
            func.upper(func.trim(Customer.customer_code)) == "PHR",
        ),
    ).limit(2).all()
    if len(matches) > 1:
        raise HTTPException(409, "Ambiguous active PHR customer master; resolve before preparing AR")
    return matches[0] if matches else None


def available_accounts(db: Session) -> dict:
    unit = db.query(BusinessUnit).filter(
        BusinessUnit.code == "002", BusinessUnit.is_active.is_(True)
    ).first()
    customer = phr_customer(db)
    all_accounts = db.query(ChartOfAccount).filter(
        ChartOfAccount.is_active.is_(True), ChartOfAccount.is_posting.is_(True)
    ).order_by(ChartOfAccount.account_number).all()
    def encode(row):
        return {
            "id": row.id, "code": row.account_number,
            "name": row.account_name,
        }
    eligible_revenue = {r.id for r in revenue_accounts(db, unit.id).all()} if unit else set()
    return {
        "confirmed_customer": (
            {"id": customer.id, "code": customer.customer_code, "name": customer.customer_name}
            if customer else None
        ),
        "business_unit_code": "002",
        "ar_accounts": [encode(a) for a in all_accounts if (
            a.account_type == "ASSET" and a.normal_balance == "DEBIT"
            and a.account_number.startswith("100-200-")
        )],
        "revenue_accounts": [encode(a) for a in all_accounts if a.id in eligible_revenue],
        "pb1_liability_accounts": [encode(a) for a in all_accounts if (
            a.account_type == "LIABILITY" and a.normal_balance == "CREDIT"
        )],
        "cash_receipts_importable": False,
        "accounting_activation_enabled": False,
    }


def prepare_batch(
    db: Session,
    batch: ImportBatch,
    *,
    user,
    customer_id: int,
    payment_terms_days: int,
    ar_account_id: int,
    revenue_account_id: int,
    pb1_liability_account_id: int,
) -> dict:
    if batch.source != SOURCE or batch.status != "STAGED":
        raise HTTPException(409, "Only a staged historical Catering AR batch can be prepared")
    customer = phr_customer(db)
    if customer is None or customer.id != customer_id:
        raise HTTPException(422, "Select the uniquely identified active PHR customer")
    unit = db.query(BusinessUnit).filter(
        BusinessUnit.code == "002", BusinessUnit.is_active.is_(True)
    ).first()
    department = db.query(Department).filter(
        Department.code == "01", Department.is_active.is_(True)
    ).first()
    if not unit or not department or department.business_unit_id != unit.id:
        raise HTTPException(409, "Catering BU 002 and Operasional 01 are not configured")
    options = available_accounts(db)
    selected = (
        ("ar_accounts", ar_account_id),
        ("revenue_accounts", revenue_account_id),
        ("pb1_liability_accounts", pb1_liability_account_id),
    )
    for category, value in selected:
        if not any(a["id"] == value for a in options[category]):
            raise HTTPException(422, f"Selected {category} is not an active eligible posting account")
    if len({ar_account_id, revenue_account_id, pb1_liability_account_id}) != 3:
        raise HTTPException(422, "AR, revenue and PB-1 accounts must be different")

    rows = db.query(ImportRow).filter(
        ImportRow.import_batch_id == batch.id,
        ImportRow.document_type == "AR_INVOICE",
    ).order_by(ImportRow.row_number).with_for_update().all()
    if not rows:
        raise HTTPException(409, "Staging batch has no invoice rows")
    # Explicitly prevent mapping wrong business units or future unknown projects.
    codes = {str((r.normalized_data_json or {}).get("location_code") or "") for r in rows}
    locations = {
        a.code: a for a in db.query(Location).filter(Location.code.in_(codes)).all()
    }
    allowed_location_id = assigned_location_id(user)
    linked = set(
        db.query(LocationDepartment.location_id, LocationDepartment.department_id)
        .filter(LocationDepartment.department_id == department.id).all()
    )
    numbers = Counter(
        str((r.normalized_data_json or {}).get("invoice_number") or "").strip().casefold()
        for r in rows if (r.normalized_data_json or {}).get("invoice_number")
    )
    ready = blocked = warnings = 0
    for row in rows:
        normalized = dict(row.normalized_data_json or {})
        invoice_number = str(normalized.get("invoice_number") or "").strip()
        problems = list(row.error_messages_json or [])
        # A repeated preparation should not accumulate generated errors.
        problems = [v for v in problems if not v.startswith("Preparation: ")]
        site = locations.get(str(normalized.get("location_code") or ""))
        if not site or site.code not in CATERING_SITE_CODES or not site.is_active or site.business_unit_id != unit.id:
            problems.append("Preparation: Catering location missing, inactive or belongs to another Business Unit")
        elif (site.id, department.id) not in linked:
            problems.append("Preparation: Operasional department must be linked to this Catering location")
        if site and allowed_location_id is not None and allowed_location_id != site.id:
            problems.append("Preparation: User is not allowed to access this invoice location")
        if not invoice_number or len(invoice_number) > 50:
            problems.append("Preparation: External invoice number must be 1–50 characters")
        if invoice_number and numbers[invoice_number.casefold()] != 1:
            problems.append("Preparation: Duplicate external invoice number within staged source")
        if invoice_number:
            for model, attr in (
                (AccountReceivable, AccountReceivable.invoice_number),
                (SalesTransaction, SalesTransaction.transaction_number),
                (JournalEntry, JournalEntry.document_number),
            ):
                found = db.query(model.id).filter(func.lower(attr) == invoice_number.lower()).first()
                if found:
                    problems.append(f"Preparation: Invoice already referenced in {model.__tablename__}")
        try:
            invoice_date = date.fromisoformat(normalized["invoice_date"])
            normalized["due_date"] = (invoice_date + timedelta(days=payment_terms_days)).isoformat()
        except (TypeError, KeyError, ValueError, OverflowError):
            normalized["due_date"] = None
            problems.append("Preparation: A valid invoice date is required for the due date")
        try:
            dpp = Decimal(str(normalized["dpp"]))
            pb1 = Decimal(str(normalized["pb1"]))
            gross = Decimal(str(normalized["gross"]))
            ar = Decimal(str(normalized["ar"]))
            if any(
                v < 0 or not v.is_finite() or v != v.quantize(MONEY)
                for v in (dpp, pb1, gross, ar)
            ) or gross <= 0:
                problems.append("Preparation: Amounts must be positive/zero IDR values with at most two decimals")
            if dpp + pb1 != gross or gross != ar:
                problems.append("Preparation: DPP + PB-1 must equal invoice gross and source A/R exactly")
        except (InvalidOperation, KeyError, ValueError):
            problems.append("Preparation: Invalid DPP / PB-1 / gross / A/R amount")
        normalized.update({
            "customer_id": customer.id,
            "customer_name": customer.customer_name,
            "payment_terms_days": payment_terms_days,
            "ar_account_id": ar_account_id,
            "revenue_account_id": revenue_account_id,
            "pb1_liability_account_id": pb1_liability_account_id,
            "accounting_posted": False,
            "receipts_posted": False,
        })
        row.normalized_data_json = normalized
        row.error_messages_json = list(dict.fromkeys(problems))
        row.warning_messages_json = [
            m for m in (row.warning_messages_json or [])
            if not m.startswith(UNRESOLVED_NOTES)
        ]
        row.status = "ERROR" if row.error_messages_json else "READY"
        if row.status == "READY":
            ready += 1
        else:
            blocked += 1
        if row.warning_messages_json:
            warnings += 1

    batch.valid_rows = ready
    batch.error_rows = blocked
    batch.warning_rows = warnings
    batch.notes = (
        f"PHR verified; finance-approved terms {payment_terms_days} days; "
        "AR/revenue/PB-1 account choices prepared. Invoice posting, cash receipts "
        "and GL posting remain disabled pending final approval."
    )
    return {"ready": ready, "blocked": blocked, "warnings": warnings, "customer_id": customer.id}


def journal_preview(db: Session, batch: ImportBatch) -> dict:
    """Preview only accounting entries. Never writes journal or ledger objects."""
    rows = db.query(ImportRow).filter(
        ImportRow.import_batch_id == batch.id,
        ImportRow.document_type == "AR_INVOICE",
    ).order_by(ImportRow.row_number).all()
    totals = {"ar_debit": Decimal(0), "revenue_credit": Decimal(0), "pb1_credit": Decimal(0)}
    items = []
    for row in rows:
        data = row.normalized_data_json or {}
        if row.status != "READY":
            continue
        try:
            gross = Decimal(str(data["gross"]))
            dpp = Decimal(str(data["dpp"]))
            pb1 = Decimal(str(data["pb1"]))
            ids = (
                data.get("ar_account_id"),
                data.get("revenue_account_id"),
                data.get("pb1_liability_account_id"),
            )
            if not all(ids) or gross != dpp + pb1:
                continue
        except (KeyError, InvalidOperation, TypeError):
            continue
        totals["ar_debit"] += gross
        totals["revenue_credit"] += dpp
        totals["pb1_credit"] += pb1
        items.append({
            "excel_row": row.row_number,
            "invoice_number": data["invoice_number"],
            "invoice_date": data.get("invoice_date"),
            "due_date": data.get("due_date"),
            "location_code": data.get("location_code"),
            "customer_id": data.get("customer_id"),
            "ar_account_id": ids[0],
            "revenue_account_id": ids[1],
            "pb1_liability_account_id": ids[2],
            "ar_debit": str(gross),
            "revenue_credit": str(dpp),
            "pb1_credit": str(pb1),
        })
    return {
        "batch_id": batch.id,
        "ready_count": len(items),
        "blocked_count": len(rows) - len(items),
        "totals": {k: str(v.quantize(MONEY)) for k, v in totals.items()},
        "balanced": totals["ar_debit"] == totals["revenue_credit"] + totals["pb1_credit"],
        "posting_enabled": False,
        "receipt_import_enabled": False,
        "items": items,
        "reason": "Preview only; source receipts and PPh23 are not journaled, and no AR or GL has been created.",
    }
