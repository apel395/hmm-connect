from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_any_role
from app.models.account_payable import AccountPayable
from app.models.bank_account import BankAccount
from app.models.chart_of_account import ChartOfAccount
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.payment import Payment, PaymentAllocation, PaymentFundingLine
from app.models.supplier_invoice import SupplierInvoice
from app.schemas.payment import PaymentCreate, PaymentUpdate
from app.services.accounting_posting_rule_service import AccountingPostingRuleService
from app.services.audit import record_audit
from app.services.document_context import document_context, print_metadata
from app.services.document_number import next_document_number
from app.services.general_ledger import GeneralLedgerService
from app.services.location_access import apply_location_scope, enforce_location_access

router = APIRouter(prefix="/payments", tags=["Payments"])
ZERO = Decimal("0")
OPEN_INVOICE_STATUSES = {"POSTED"}


def access(user):
    if not has_any_role(user, "FINANCE"):
        raise HTTPException(403, "Finance access required")


def get(db: Session, payment_id: int, user) -> Payment:
    payment = db.get(Payment, payment_id)
    if not payment:
        raise HTTPException(404, "Payment not found")
    enforce_location_access(user, payment.location_id)
    return payment


def invoice_balance(invoice: SupplierInvoice) -> Decimal:
    return max(
        ZERO,
        Decimal(invoice.total_amount or 0)
        - Decimal(invoice.paid_amount or 0)
        - Decimal(invoice.adjustment_amount or 0),
    )


def reserved_amount(db: Session, invoice_id: int, exclude_payment_id: int | None = None) -> Decimal:
    query = db.query(PaymentAllocation).join(Payment).filter(
        PaymentAllocation.supplier_invoice_id == invoice_id,
        Payment.status == "APPROVED",
    )
    if exclude_payment_id:
        query = query.filter(Payment.id != exclude_payment_id)
    return sum((Decimal(row.allocated_amount or 0) for row in query.all()), ZERO)


def sync_payable(db: Session, invoice: SupplierInvoice, payment_date: date | None = None):
    balance = invoice_balance(invoice)
    invoice.balance_amount = balance
    invoice.payment_status = (
        "PAID"
        if balance == ZERO
        else "PARTIALLY_PAID"
        if Decimal(invoice.paid_amount or 0) > ZERO or Decimal(invoice.adjustment_amount or 0) > ZERO
        else "UNPAID"
    )
    payable = db.query(AccountPayable).filter(
        AccountPayable.supplier_id == invoice.supplier_id,
        AccountPayable.invoice_number == invoice.internal_invoice_number,
    ).first()
    if payable:
        payable.amount = invoice.total_amount
        payable.paid_amount = invoice.paid_amount
        payable.outstanding_amount = balance
        payable.payment_status = invoice.payment_status
        payable.status = "PAID" if balance == ZERO else "OPEN"
        if payment_date:
            payable.last_payment_date = payment_date
    return balance


def validate_data(db: Session, data: PaymentCreate, user, exclude: int | None = None):
    invoices = []
    seen_invoice_ids: set[int] = set()
    for allocation in data.allocations:
        if allocation.supplier_invoice_id in seen_invoice_ids:
            raise HTTPException(422, "The same supplier invoice cannot be allocated more than once")
        seen_invoice_ids.add(allocation.supplier_invoice_id)

        invoice = db.get(SupplierInvoice, allocation.supplier_invoice_id)
        if not invoice or invoice.supplier_id != data.supplier_id:
            raise HTTPException(400, "Allocated invoice does not belong to selected supplier")
        enforce_location_access(user, invoice.location_id)
        if invoice.status not in OPEN_INVOICE_STATUSES or invoice.payment_status == "PAID":
            raise HTTPException(409, "Only posted unpaid invoices can be allocated")
        if invoice.currency != data.currency.upper():
            raise HTTPException(400, "Payment and invoice currencies must match")

        available = invoice_balance(invoice) - reserved_amount(db, invoice.id, exclude)
        if Decimal(allocation.allocated_amount) <= ZERO:
            raise HTTPException(422, "Payment allocation must be greater than zero")
        if Decimal(allocation.allocated_amount) > available:
            raise HTTPException(
                409,
                f"Allocation exceeds available balance for {invoice.internal_invoice_number}: {available}",
            )
        invoices.append(invoice)

    bank_accounts = []
    for funding in data.funding_lines:
        bank = db.get(BankAccount, funding.bank_account_id)
        if not bank or not bank.is_active:
            raise HTTPException(422, "Funding bank account must be active")
        if bank.currency != data.currency.upper():
            raise HTTPException(422, "Funding bank account currency must match payment currency")
        linked_account = bank.coa_account
        if (
            not linked_account
            or not linked_account.is_active
            or not linked_account.is_posting
            or linked_account.account_type != "ASSET"
            or linked_account.account_subtype not in {"BANK", "CASH", "PETTY_CASH"}
        ):
            raise HTTPException(
                422,
                "Funding bank account must have an active BANK/CASH posting COA",
            )
        if Decimal(funding.amount) <= ZERO:
            raise HTTPException(422, "Funding amount must be greater than zero")
        bank_accounts.append(bank)

    allocated_total = sum((Decimal(row.allocated_amount) for row in data.allocations), ZERO)
    funded_total = sum((Decimal(row.amount) for row in data.funding_lines), ZERO)
    total = Decimal(data.total_amount)
    if allocated_total != total:
        raise HTTPException(422, "Allocations must equal payment total")
    if funded_total != total:
        raise HTTPException(422, "Funding lines must equal payment total")

    if invoices:
        source = invoices[0]
        for invoice in invoices[1:]:
            if invoice.business_unit_id != source.business_unit_id:
                raise HTTPException(422, "A payment cannot combine invoices from different Business Units")
            if invoice.location_id != source.location_id:
                raise HTTPException(422, "A payment cannot combine invoices from different Locations")
            if invoice.department_id != source.department_id:
                raise HTTPException(422, "A payment cannot combine invoices from different Departments")
        data.business_unit_id = source.business_unit_id
        data.location_id = source.location_id
        data.department_id = source.department_id
        for bank in bank_accounts:
            if bank.business_unit_id != source.business_unit_id:
                raise HTTPException(
                    422,
                    "Funding bank account must belong to the invoice Business Unit",
                )
            if bank.location_id is not None and bank.location_id != source.location_id:
                raise HTTPException(
                    422,
                    "Funding bank account is restricted to a different Location",
                )
    return invoices, bank_accounts


def validate_payment_journal_integrity(db: Session, payment: Payment, journal: JournalEntry):
    rule = AccountingPostingRuleService(db).select_rule(
        "SUPPLIER_PAYMENT",
        payment.business_unit_id,
        payment.location_id,
    )
    if not rule:
        raise HTTPException(
            409,
            "No active SUPPLIER_PAYMENT posting rule configured for this Business Unit and Location",
        )

    if (
        journal.reference_type != "SUPPLIER_PAYMENT"
        or journal.reference_id != payment.id
        or journal.document_number != payment.payment_number
        or journal.business_unit_id != payment.business_unit_id
        or journal.location_id != payment.location_id
        or journal.department_id != payment.department_id
    ):
        raise HTTPException(409, "Payment journal context does not match its source payment")

    expected_debits = {rule.debit_account_id: Decimal(payment.amount)}
    expected_credits = defaultdict(Decimal)
    funding_accounts = []
    for funding in payment.funding_lines:
        account = funding.bank_account.coa_account
        if (
            not account
            or not account.is_active
            or not account.is_posting
            or account.account_type != "ASSET"
            or account.account_subtype not in {"BANK", "CASH", "PETTY_CASH"}
        ):
            raise HTTPException(
                409,
                "Payment funding bank account has no valid linked BANK/CASH posting COA",
            )
        expected_credits[account.id] += Decimal(funding.amount)
        funding_accounts.append(account)

    actual_debits = defaultdict(Decimal)
    actual_credits = defaultdict(Decimal)
    for line in journal.lines:
        debit = Decimal(line.debit or 0)
        credit = Decimal(line.credit or 0)
        if debit < ZERO or credit < ZERO or (debit > ZERO and credit > ZERO):
            raise HTTPException(409, "Payment journal contains an invalid debit/credit line")
        if (
            line.business_unit_id != payment.business_unit_id
            or line.location_id != payment.location_id
            or line.department_id != payment.department_id
        ):
            raise HTTPException(409, "Payment journal line dimensions do not match the source payment")
        if debit:
            actual_debits[line.account_id] += debit
        if credit:
            actual_credits[line.account_id] += credit

    if dict(actual_debits) != expected_debits:
        raise HTTPException(
            409,
            "Payment journal debit must match the scoped Accounts Payable control account and payment total",
        )
    if dict(actual_credits) != dict(expected_credits):
        raise HTTPException(
            409,
            "Payment journal credit must match the selected funding accounts and amounts",
        )

    AccountingPostingRuleService.validate_source_journal_accounts(
        "SUPPLIER_PAYMENT",
        [rule.debit_account],
        funding_accounts,
    )
    return rule


def serialize(payment: Payment):
    allocated = sum((Decimal(row.allocated_amount) for row in payment.allocations), ZERO)
    funded = sum((Decimal(row.amount) for row in payment.funding_lines), ZERO)
    return {
        "id": payment.id,
        "payment_number": payment.payment_number,
        "supplier_id": payment.supplier_id,
        "supplier_name": payment.supplier.name if payment.supplier else None,
        "payment_date": payment.payment_date,
        "payment_method": payment.payment_method,
        "currency": payment.currency,
        "total_amount": payment.amount,
        "allocated_amount": allocated,
        "funded_amount": funded,
        "business_unit_id": payment.business_unit_id,
        "location_id": payment.location_id,
        "department_id": payment.department_id,
        "reference_number": payment.reference_number,
        "cheque_number": payment.cheque_number,
        "status": payment.status,
        "notes": payment.notes,
        "source_type": payment.source_type,
        "journal_entry_id": payment.journal_entry_id,
        "journal_number": payment.journal_entry.journal_number if payment.journal_entry else None,
        "created_by_name": payment.created_by.full_name if payment.created_by else None,
        "approved_by_name": payment.approved_by.full_name if payment.approved_by else None,
        "posted_by_name": payment.posted_by.full_name if payment.posted_by else None,
        "created_at": payment.created_at,
        "updated_at": payment.updated_at,
        "approved_at": payment.approved_at,
        "posted_at": payment.posted_at,
        "voided_at": payment.voided_at,
        "allocations": [{
            "id": row.id,
            "supplier_invoice_id": row.supplier_invoice_id,
            "invoice_number": row.supplier_invoice.internal_invoice_number,
            "supplier_invoice_number": row.supplier_invoice.supplier_invoice_number,
            "invoice_date": row.supplier_invoice.invoice_date,
            "due_date": row.supplier_invoice.due_date,
            "invoice_total": row.supplier_invoice.total_amount,
            "paid_amount": row.supplier_invoice.paid_amount,
            "outstanding_balance": row.supplier_invoice.balance_amount,
            "allocated_amount": row.allocated_amount,
        } for row in payment.allocations],
        "funding_lines": [{
            "id": row.id,
            "bank_account_id": row.bank_account_id,
            "bank_name": row.bank_account.bank_name,
            "account_name": row.bank_account.account_name,
            "account_number": row.bank_account.account_number,
            "coa_account_id": row.bank_account.coa_account_id,
            "amount": row.amount,
        } for row in payment.funding_lines],
    }


def result(db, payment, user):
    data = serialize(payment)
    data.update(document_context(db, "PAYMENT", payment.id, payment.status, user))
    data["allowed_actions"] = {
        "can_edit": payment.status == "DRAFT",
        "can_approve": payment.status == "DRAFT",
        "can_generate_journal": payment.status == "APPROVED" and not payment.journal_entry_id,
        "can_post": payment.status == "APPROVED" and bool(payment.journal_entry_id and payment.journal_entry.status == "DRAFT"),
        "can_void": payment.status in {"DRAFT", "APPROVED"},
        "can_print": True,
        "can_manage_attachments": True,
        "can_view_history": True,
    }
    return data


@router.get("")
def listing(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    supplier_id: int | None = None,
    status: str | None = None,
    payment_method: str | None = None,
    payment_date_from: date | None = None,
    payment_date_to: date | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    access(user)
    query = apply_location_scope(db.query(Payment), Payment, user)
    if search:
        query = query.filter(or_(Payment.payment_number.ilike(f"%{search}%"), Payment.reference_number.ilike(f"%{search}%")))
    if supplier_id:
        query = query.filter(Payment.supplier_id == supplier_id)
    if status:
        query = query.filter(Payment.status == status)
    if payment_method:
        query = query.filter(Payment.payment_method == payment_method)
    if payment_date_from:
        query = query.filter(Payment.payment_date >= payment_date_from)
    if payment_date_to:
        query = query.filter(Payment.payment_date <= payment_date_to)
    total = query.count()
    rows = query.order_by(Payment.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [serialize(row) for row in rows],
        "page": page,
        "page_size": page_size,
        "total_items": total,
        "total_pages": ceil(total / page_size) if total else 0,
        "has_next": page * page_size < total,
        "has_previous": page > 1,
    }


@router.get("/eligible-invoices")
def eligible(supplier_id: int, currency: str = "IDR", db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    rows = apply_location_scope(db.query(SupplierInvoice), SupplierInvoice, user).filter(
        SupplierInvoice.supplier_id == supplier_id,
        SupplierInvoice.currency == currency.upper(),
        SupplierInvoice.status.in_(OPEN_INVOICE_STATUSES),
    ).order_by(SupplierInvoice.due_date.asc().nullslast(), SupplierInvoice.id).all()

    available_rows = []
    for row in rows:
        outstanding = invoice_balance(row)
        reserved = reserved_amount(db, row.id)
        available = max(ZERO, outstanding - reserved)
        if available == ZERO:
            continue
        available_rows.append({
            "id": row.id,
            "invoice_number": row.internal_invoice_number,
            "supplier_invoice_number": row.supplier_invoice_number,
            "invoice_date": row.invoice_date,
            "due_date": row.due_date,
            "total_amount": row.total_amount,
            "paid_amount": row.paid_amount,
            "outstanding_balance": outstanding,
            "reserved_amount": reserved,
            "available_balance": available,
            "currency": row.currency,
            "business_unit_id": row.business_unit_id,
            "location_id": row.location_id,
            "department_id": row.department_id,
        })
    return available_rows


@router.get("/{payment_id}")
def detail(payment_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    return result(db, get(db, payment_id, user), user)


@router.post("", status_code=201)
def create(data: PaymentCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    validate_data(db, data, user)
    payment = Payment(
        payment_number=next_document_number(db, "PAY"),
        supplier_id=data.supplier_id,
        payment_date=data.payment_date,
        amount=data.total_amount,
        payment_method=data.payment_method,
        currency=data.currency.upper(),
        reference_number=data.reference_number,
        cheque_number=data.cheque_number,
        notes=data.notes,
        source_type=data.source_type,
        status="DRAFT",
        created_by_id=user.id,
        business_unit_id=data.business_unit_id,
        location_id=data.location_id,
        department_id=data.department_id,
    )
    payment.allocations = [PaymentAllocation(**row.model_dump()) for row in data.allocations]
    payment.funding_lines = [PaymentFundingLine(**row.model_dump()) for row in data.funding_lines]
    db.add(payment)
    db.flush()
    record_audit(db, user, "PAYMENT_CREATED", "PAYMENT", f"Created {payment.payment_number}", entity_id=payment.id)
    db.commit()
    db.refresh(payment)
    return result(db, payment, user)


@router.patch("/{payment_id}")
def update(payment_id: int, data: PaymentUpdate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    payment = get(db, payment_id, user)
    if payment.status != "DRAFT":
        raise HTTPException(409, "Only draft payments can be edited")
    validate_data(db, data, user, payment.id)
    payment.supplier_id = data.supplier_id
    payment.payment_date = data.payment_date
    payment.amount = data.total_amount
    payment.payment_method = data.payment_method
    payment.currency = data.currency.upper()
    payment.reference_number = data.reference_number
    payment.cheque_number = data.cheque_number
    payment.notes = data.notes
    payment.business_unit_id = data.business_unit_id
    payment.location_id = data.location_id
    payment.department_id = data.department_id
    payment.allocations.clear()
    payment.funding_lines.clear()
    payment.allocations = [PaymentAllocation(**row.model_dump()) for row in data.allocations]
    payment.funding_lines = [PaymentFundingLine(**row.model_dump()) for row in data.funding_lines]
    db.commit()
    db.refresh(payment)
    return result(db, payment, user)


@router.post("/{payment_id}/approve")
def approve(payment_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    payment = db.query(Payment).filter(Payment.id == payment_id).with_for_update().first()
    if not payment or payment.status != "DRAFT":
        raise HTTPException(409, "Only draft payments can be approved")
    enforce_location_access(user, payment.location_id)

    # Re-check every invoice at approval time so another approved payment cannot reserve it first.
    for allocation in payment.allocations:
        invoice = db.query(SupplierInvoice).filter(SupplierInvoice.id == allocation.supplier_invoice_id).with_for_update().one()
        if invoice.status not in OPEN_INVOICE_STATUSES:
            raise HTTPException(409, f"Invoice {invoice.internal_invoice_number} is not posted and cannot be paid")
        available = invoice_balance(invoice) - reserved_amount(db, invoice.id, payment.id)
        if Decimal(allocation.allocated_amount) > available:
            raise HTTPException(409, f"Invoice {invoice.internal_invoice_number} only has {available} available")

    if sum((Decimal(row.allocated_amount) for row in payment.allocations), ZERO) != Decimal(payment.amount):
        raise HTTPException(409, "Allocations must equal payment total")
    if sum((Decimal(row.amount) for row in payment.funding_lines), ZERO) != Decimal(payment.amount):
        raise HTTPException(409, "Funding lines must equal payment total")
    payment.status = "APPROVED"
    payment.approved_by_id = user.id
    payment.approved_at = datetime.now(timezone.utc)
    record_audit(db, user, "PAYMENT_APPROVED", "PAYMENT", f"Approved {payment.payment_number}", entity_id=payment.id)
    db.commit()
    db.refresh(payment)
    return result(db, payment, user)


@router.post("/{payment_id}/generate-journal")
def generate(payment_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    payment = get(db, payment_id, user)
    if payment.status != "APPROVED":
        raise HTTPException(409, "Payment must be approved")
    if payment.journal_entry_id:
        raise HTTPException(409, "Payment already has a journal")
    for allocation in payment.allocations:
        if allocation.supplier_invoice.status not in OPEN_INVOICE_STATUSES:
            raise HTTPException(409, f"Invoice {allocation.supplier_invoice.internal_invoice_number} is not posted")
    rule = AccountingPostingRuleService(db).select_rule(
        "SUPPLIER_PAYMENT",
        payment.business_unit_id,
        payment.location_id,
    )
    if not rule:
        raise HTTPException(
            409,
            "No active SUPPLIER_PAYMENT posting rule configured for this Business Unit and Location",
        )
    funding_accounts = [
        db.get(ChartOfAccount, funding.bank_account.coa_account_id)
        for funding in payment.funding_lines
    ]
    if any(account is None for account in funding_accounts):
        raise HTTPException(409, "Payment funding bank account is missing its linked COA")
    AccountingPostingRuleService.validate_source_journal_accounts(
        "SUPPLIER_PAYMENT",
        [rule.debit_account],
        funding_accounts,
    )
    journal = JournalEntry(
        journal_number=next_document_number(db, "JV"),
        posting_date=payment.payment_date,
        status="DRAFT",
        document_type="SUPPLIER_PAYMENT",
        document_number=payment.payment_number,
        reference_type="SUPPLIER_PAYMENT",
        reference_id=payment.id,
        description=f"Supplier payment {payment.payment_number}",
        created_by_id=user.id,
        business_unit_id=payment.business_unit_id,
        location_id=payment.location_id,
        department_id=payment.department_id,
    )
    category = rule.debit_account.cash_flow_category if rule.debit_account.cash_flow_category in {"OPERATING", "INVESTING", "FINANCING"} else "OPERATING"
    journal.lines.append(JournalLine(
        line_number=1,
        account_id=rule.debit_account_id,
        debit=payment.amount,
        credit=0,
        description="Accounts Payable",
        supplier_id=payment.supplier_id,
        business_unit_id=payment.business_unit_id,
        location_id=payment.location_id,
        department_id=payment.department_id,
        cash_flow_category=category,
        cash_flow_direction="OUTFLOW",
    ))
    for index, funding in enumerate(payment.funding_lines, 2):
        journal.lines.append(JournalLine(
            line_number=index,
            account_id=funding.bank_account.coa_account_id,
            debit=0,
            credit=funding.amount,
            description=f"{funding.bank_account.bank_name} - {funding.bank_account.account_name}",
            supplier_id=payment.supplier_id,
            business_unit_id=payment.business_unit_id,
            location_id=payment.location_id,
            department_id=payment.department_id,
            cash_flow_category=category,
            cash_flow_direction="OUTFLOW",
        ))
    validate_payment_journal_integrity(db, payment, journal)
    db.add(journal)
    db.flush()
    payment.journal_entry_id = journal.id
    record_audit(db, user, "PAYMENT_JOURNAL_GENERATED", "PAYMENT", f"Generated {journal.journal_number} for {payment.payment_number}", entity_id=payment.id)
    db.commit()
    db.refresh(payment)
    return result(db, payment, user)


@router.post("/{payment_id}/post")
def post(payment_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    payment = db.query(Payment).filter(Payment.id == payment_id).with_for_update().first()
    if not payment or payment.status != "APPROVED" or not payment.journal_entry_id:
        raise HTTPException(409, "Approved payment with draft journal required")
    enforce_location_access(user, payment.location_id)
    journal = db.query(JournalEntry).filter(JournalEntry.id == payment.journal_entry_id).with_for_update().one()
    if journal.status != "DRAFT":
        raise HTTPException(409, "Payment journal is not draft")
    validate_payment_journal_integrity(db, payment, journal)
    debit = sum((Decimal(line.debit) for line in journal.lines), ZERO)
    credit = sum((Decimal(line.credit) for line in journal.lines), ZERO)
    if debit != credit or debit != Decimal(payment.amount):
        raise HTTPException(409, "Payment journal is not balanced")

    for allocation in payment.allocations:
        invoice = db.query(SupplierInvoice).filter(SupplierInvoice.id == allocation.supplier_invoice_id).with_for_update().one()
        if invoice.status not in OPEN_INVOICE_STATUSES:
            raise HTTPException(409, f"Invoice {invoice.internal_invoice_number} is not posted and payment cannot be posted")
        amount = Decimal(allocation.allocated_amount)
        current_balance = invoice_balance(invoice)
        if amount > current_balance:
            raise HTTPException(409, f"Allocation exceeds current balance for {invoice.internal_invoice_number}")
        invoice.paid_amount = Decimal(invoice.paid_amount or 0) + amount
        sync_payable(db, invoice, payment.payment_date)

    for line in journal.lines:
        GeneralLedgerService.post(
            db=db,
            account_id=line.account_id,
            debit=line.debit,
            credit=line.credit,
            posting_date=journal.posting_date,
            journal_source="SUPPLIER_PAYMENT",
            document_type=journal.document_type,
            document_number=journal.document_number,
            reference_type=journal.reference_type,
            reference_id=journal.reference_id,
            reference_number=journal.journal_number,
            description=line.description,
            user_id=user.id,
        )

    now = datetime.now(timezone.utc)
    journal.status = "POSTED"
    journal.posted_by_id = user.id
    journal.posted_at = now
    payment.status = "POSTED"
    payment.posted_by_id = user.id
    payment.posted_at = now
    record_audit(db, user, "PAYMENT_POSTED", "PAYMENT", f"Posted {payment.payment_number}", entity_id=payment.id, reference_document=journal.journal_number)
    db.commit()
    db.refresh(payment)
    return result(db, payment, user)


@router.post("/{payment_id}/void")
def void(payment_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    payment = get(db, payment_id, user)
    if payment.status == "POSTED":
        raise HTTPException(409, "Posted payments require a reversal and cannot be voided")
    if payment.status == "VOID":
        raise HTTPException(409, "Payment is already void")
    payment.status = "VOID"
    payment.voided_at = datetime.now(timezone.utc)
    if payment.journal_entry and payment.journal_entry.status == "DRAFT":
        payment.journal_entry.status = "VOID"
        payment.journal_entry.voided_at = payment.voided_at
    db.commit()
    db.refresh(payment)
    return result(db, payment, user)


@router.get("/{payment_id}/allowed-actions")
def actions(payment_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    return result(db, get(db, payment_id, user), user)["allowed_actions"]


@router.get("/{payment_id}/print")
def printable(payment_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    return {**result(db, get(db, payment_id, user), user), "document_type": "Supplier Payment", **print_metadata(user)}