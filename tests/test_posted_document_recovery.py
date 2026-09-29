from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1 import payments, supplier_invoices
from app.models import Base
from app.models.account_payable import AccountPayable
from app.models.bank_account import BankAccount
from app.models.chart_of_account import ChartOfAccount
from app.models.general_ledger import GeneralLedger
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.payment import Payment, PaymentAllocation, PaymentFundingLine
from app.models.supplier import Supplier
from app.models.supplier_invoice import SupplierInvoice, SupplierInvoiceLine
from app.services.fiscal_period_service import FiscalPeriodService


ADMIN = SimpleNamespace(
    id=1, roles=[SimpleNamespace(name="SYSTEM_ADMINISTRATOR")],
    default_location_id=None, location_id=None,
)


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    monkeypatch.setattr(FiscalPeriodService, "validate_posting_date", staticmethod(lambda db, posting_date: None))
    yield session
    session.close()
    engine.dispose()


def _account(db, code, kind, subtype="OTHER"):
    account = ChartOfAccount(
        account_number=code, account_name=code, account_type=kind,
        account_subtype=subtype, normal_balance="CREDIT" if kind == "LIABILITY" else "DEBIT",
        is_active=True, is_posting=True,
    )
    db.add(account)
    db.flush()
    return account


def _journal(db, reference_type, reference_id, document_number, debit_id, credit_id):
    journal = JournalEntry(
        journal_number=f"PAY-TEST-JV-{reference_type}", posting_date=date(2026, 9, 29),
        status="POSTED", reference_type=reference_type, reference_id=reference_id,
        document_type=reference_type, document_number=document_number, location_id=1,
    )
    journal.lines = [
        JournalLine(account_id=debit_id, debit=Decimal("111"), credit=0, location_id=1),
        JournalLine(account_id=credit_id, debit=0, credit=Decimal("111"), location_id=1),
    ]
    db.add(journal)
    db.flush()
    for index, account_id, debit, credit in (
        (1, debit_id, Decimal("111"), Decimal("0")),
        (2, credit_id, Decimal("0"), Decimal("111")),
    ):
        db.add(GeneralLedger(
            journal_number=f"PAY-TEST-GL-{reference_type}-{index}",
            posting_date=date(2026, 9, 29), account_id=account_id,
            debit=debit, credit=credit, reference_type=reference_type,
            reference_id=reference_id, reference_number=journal.journal_number,
        ))
    db.commit()
    return journal


def test_cancel_posted_orphan_payment_voids_journal_and_removes_ledger(db):
    payable = _account(db, "PAY-AP", "LIABILITY")
    cash = _account(db, "PAY-BANK", "ASSET", "BANK")
    supplier = Supplier(code="PAY-CANCEL", name="Supplier", is_active=True)
    db.add(supplier)
    db.flush()
    bank = BankAccount(
        bank_name="Test Bank", account_name="Operating", account_number="PAY-CANCEL-BANK",
        coa_account_id=cash.id, business_unit_id=1, is_active=True, is_payment_account=True,
    )
    db.add(bank)
    db.flush()
    payment = Payment(
        payment_number="PAY-CANCEL-1", supplier_id=supplier.id,
        payment_date=date(2026, 9, 29), amount=Decimal("111"),
        payment_method="BANK_TRANSFER", status="POSTED", created_by_id=1, location_id=1,
    )
    payment.funding_lines = [PaymentFundingLine(bank_account_id=bank.id, amount=Decimal("111"))]
    db.add(payment)
    db.flush()
    journal = _journal(db, "SUPPLIER_PAYMENT", payment.id, payment.payment_number, payable.id, cash.id)
    payment.journal_entry_id = journal.id
    db.commit()

    result = payments.cancel_posted(payment.id, db=db, user=ADMIN)
    db.refresh(payment)
    db.refresh(journal)
    assert result["status"] == "VOID"
    assert payment.status == "VOID"
    assert journal.status == "VOID"
    assert db.query(GeneralLedger).filter(GeneralLedger.reference_id == payment.id).count() == 0
    assert payment.allocations == []
    with pytest.raises(Exception):
        payments.cancel_posted(payment.id, db=db, user=ADMIN)


def test_invoice_unpost_then_reopen_voids_old_journal(db, monkeypatch):
    debit = _account(db, "INV-EXP", "EXPENSE")
    payable = _account(db, "INV-AP", "LIABILITY")
    supplier = Supplier(code="INV-RECOVER", name="Supplier", is_active=True)
    db.add(supplier)
    db.flush()
    invoice = SupplierInvoice(
        internal_invoice_number="INV-RECOVER-1", supplier_invoice_number="RECOVER-1",
        supplier_id=supplier.id, invoice_date=date(2026, 9, 29),
        subtotal=Decimal("111"), total_amount=Decimal("111"),
        status="POSTED", location_id=1,
    )
    db.add(invoice)
    db.flush()
    journal = _journal(db, "SUPPLIER_INVOICE", invoice.id, invoice.internal_invoice_number, debit.id, payable.id)
    monkeypatch.setattr(supplier_invoices, "result", lambda db, invoice, user: {"status": invoice.status})

    assert supplier_invoices.admin_unpost(invoice.id, db=db, user=ADMIN)["status"] == "VERIFIED"
    db.refresh(journal)
    assert journal.status == "DRAFT"
    assert db.query(GeneralLedger).filter(GeneralLedger.reference_type == "SUPPLIER_INVOICE").count() == 0
    assert supplier_invoices.admin_reopen(invoice.id, db=db, user=ADMIN)["status"] == "DRAFT"
    db.refresh(journal)
    assert journal.status == "VOID"


def test_cancel_posted_payment_restores_invoice_and_ap_last_payment_date(db):
    payable_account = _account(db, "PAY-AP-2", "LIABILITY")
    cash_account = _account(db, "PAY-BANK-2", "ASSET", "BANK")
    supplier = Supplier(code="PAY-RESTORE", name="Supplier", is_active=True)
    db.add(supplier)
    db.flush()
    bank = BankAccount(
        bank_name="Second Bank", account_name="Operating", account_number="PAY-RESTORE-BANK",
        coa_account_id=cash_account.id, business_unit_id=1,
        is_active=True, is_payment_account=True,
    )
    db.add(bank)
    db.flush()
    invoice = SupplierInvoice(
        internal_invoice_number="PAY-RESTORE-INV", supplier_invoice_number="RESTORE",
        supplier_id=supplier.id, invoice_date=date(2026, 9, 1),
        subtotal=Decimal("100"), tax_amount=Decimal("11"),
        total_amount=Decimal("111"), paid_amount=Decimal("111"),
        balance_amount=Decimal("0"), status="POSTED", location_id=1,
    )
    invoice.lines = [SupplierInvoiceLine(
        description="Taxable supply", quantity=1, unit_price=Decimal("100"),
        line_amount=Decimal("100"), is_taxable=True,
        tax_rate=Decimal("11"), tax_amount=Decimal("11"),
    )]
    db.add(invoice)
    db.flush()
    mirror = AccountPayable(
        supplier_id=supplier.id, invoice_number=invoice.internal_invoice_number,
        amount=Decimal("111"), paid_amount=Decimal("111"),
        outstanding_amount=Decimal("0"), status="PAID", payment_status="PAID",
        last_payment_date=date(2026, 9, 29),
    )
    db.add(mirror)
    payment = Payment(
        payment_number="PAY-RESTORE-1", supplier_id=supplier.id,
        payment_date=date(2026, 9, 29), amount=Decimal("111"),
        payment_method="BANK_TRANSFER", status="POSTED", created_by_id=1, location_id=1,
    )
    payment.allocations = [PaymentAllocation(supplier_invoice_id=invoice.id, allocated_amount=Decimal("111"))]
    payment.funding_lines = [PaymentFundingLine(bank_account_id=bank.id, amount=Decimal("111"))]
    db.add(payment)
    db.flush()
    journal = _journal(db, "SUPPLIER_PAYMENT", payment.id, payment.payment_number, payable_account.id, cash_account.id)
    payment.journal_entry_id = journal.id
    db.commit()

    payments.cancel_posted(payment.id, db=db, user=ADMIN)
    db.refresh(invoice)
    db.refresh(mirror)
    assert invoice.paid_amount == Decimal("0")
    assert invoice.balance_amount == Decimal("111")
    assert mirror.outstanding_amount == Decimal("111")
    assert mirror.last_payment_date is None
