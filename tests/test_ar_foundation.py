from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.account_receivable import AccountReceivable
from app.models.accounting_posting_rule import AccountingPostingRule
from app.models.chart_of_account import ChartOfAccount
from app.models.customer import Customer
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.user import User
from app.api.v1 import customer_payments as customer_payment_api
from app.schemas.customer_payment import CustomerPaymentCreate
from app.services.financial_reconciliation_service import FinancialReconciliationService
from app.services.journal_service import JournalService
from app.services.posting_service import PostingService


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()


def account(db, number, name):
    row = ChartOfAccount(
        account_number=number,
        account_name=name,
        account_type="ASSET",
        normal_balance="DEBIT",
        is_posting=True,
        is_active=True,
    )
    db.add(row)
    db.flush()
    return row


def test_customer_payment_uses_configured_accounts(db, monkeypatch):
    cash = account(db, "1000", "Cash")
    receivable = account(db, "1200", "Accounts Receivable")
    db.add(AccountingPostingRule(
        event_type="CUSTOMER_PAYMENT",
        debit_account_id=cash.id,
        credit_account_id=receivable.id,
        is_active=True,
    ))
    db.flush()

    captured = {}

    def capture_post(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(id=99)

    monkeypatch.setattr(JournalService, "post", capture_post)
    payment = SimpleNamespace(
        id=7,
        payment_number="CP-000007",
        payment_date=date(2026, 8, 21),
        amount=Decimal("250000.00"),
    )

    result = PostingService.post_customer_payment(
        db=db,
        payment=payment,
        receivable=SimpleNamespace(id=3),
        user=SimpleNamespace(id=1),
    )

    assert result.id == 99
    journal = captured["journal"]
    assert journal.document_type == "CUSTOMER_PAYMENT"
    assert journal.lines[0].account_id == cash.id
    assert journal.lines[0].debit == Decimal("250000.00")
    assert journal.lines[1].account_id == receivable.id
    assert journal.lines[1].credit == Decimal("250000.00")


def test_customer_payment_requires_active_rule(db):
    payment = SimpleNamespace(
        id=1,
        payment_number="CP-000001",
        payment_date=date(2026, 8, 21),
        amount=Decimal("1.00"),
    )

    with pytest.raises(HTTPException) as error:
        PostingService.post_customer_payment(
            db=db,
            payment=payment,
            receivable=SimpleNamespace(id=1),
            user=SimpleNamespace(id=1),
        )

    assert error.value.status_code == 409
    assert "CUSTOMER_PAYMENT" in error.value.detail


def test_ar_reconciliation_uses_rule_credit_account(db):
    cash = account(db, "1000", "Cash")
    receivable_account = account(db, "1200", "Accounts Receivable")
    db.add(AccountingPostingRule(
        event_type="CUSTOMER_PAYMENT",
        debit_account_id=cash.id,
        credit_account_id=receivable_account.id,
        is_active=True,
    ))
    customer = Customer(
        customer_code="CUS-1",
        customer_name="Customer",
        is_active=True,
    )
    db.add(customer)
    db.flush()
    db.add(AccountReceivable(
        invoice_number="AR-1",
        customer_id=customer.id,
        invoice_date=date(2026, 8, 21),
        due_date=date(2026, 9, 21),
        amount=Decimal("100000.00"),
        received_amount=Decimal("0.00"),
        outstanding_amount=Decimal("100000.00"),
        status="UNPAID",
    ))
    entry = JournalEntry(
        journal_number="JV-AR-1",
        posting_date=date(2026, 8, 21),
        status="POSTED",
        reference_type="CUSTOMER_INVOICE",
        reference_id=1,
    )
    entry.lines.append(JournalLine(
        account_id=receivable_account.id,
        debit=Decimal("100000.00"),
        credit=Decimal("0.00"),
    ))
    db.add(entry)
    db.commit()

    row = FinancialReconciliationService(db).accounts_receivable()

    assert row["source_balance"] == Decimal("100000.00")
    assert row["gl_balance"] == Decimal("100000.00")
    assert row["difference"] == Decimal("0.00")
    assert row["status"] == "RECONCILED"
    assert row["accounts"][0]["account_id"] == receivable_account.id


def test_customer_payment_amount_must_be_positive():
    with pytest.raises(ValidationError):
        CustomerPaymentCreate(
            account_receivable_id=1,
            payment_date=date(2026, 8, 21),
            amount=Decimal("0"),
            payment_method="BANK_TRANSFER",
        )


def test_customer_payment_updates_balance_atomically(db, monkeypatch):
    customer = Customer(customer_code="CUS-PAY", customer_name="Customer", is_active=True)
    user = User(
        username="finance-ar",
        email="finance-ar@example.test",
        full_name="Finance AR",
        password_hash="x",
        is_active=True,
    )
    db.add_all([customer, user])
    db.flush()
    receivable = AccountReceivable(
        invoice_number="AR-PAY",
        customer_id=customer.id,
        invoice_date=date(2026, 8, 21),
        due_date=date(2026, 9, 21),
        amount=Decimal("100000.00"),
        received_amount=Decimal("0.00"),
        outstanding_amount=Decimal("100000.00"),
        status="UNPAID",
    )
    db.add(receivable)
    db.commit()

    monkeypatch.setattr(customer_payment_api, "next_document_number", lambda *_args, **_kwargs: "CP-202608-0001")
    monkeypatch.setattr(PostingService, "post_customer_payment", lambda **_kwargs: None)

    payment = customer_payment_api.create_customer_payment(
        CustomerPaymentCreate(
            account_receivable_id=receivable.id,
            payment_date=date(2026, 8, 21),
            amount=Decimal("40000.00"),
            payment_method="BANK_TRANSFER",
        ),
        db,
        user,
    )

    assert payment.payment_number == "CP-202608-0001"
    assert receivable.received_amount == Decimal("40000.00")
    assert receivable.outstanding_amount == Decimal("60000.00")
    assert receivable.status == "PARTIAL"


def test_customer_payment_rejects_overpayment_without_balance_mutation(db):
    customer = Customer(customer_code="CUS-LIMIT", customer_name="Customer", is_active=True)
    db.add(customer)
    db.flush()
    receivable = AccountReceivable(
        invoice_number="AR-LIMIT",
        customer_id=customer.id,
        invoice_date=date(2026, 8, 21),
        due_date=date(2026, 9, 21),
        amount=Decimal("100.00"),
        received_amount=Decimal("0.00"),
        outstanding_amount=Decimal("100.00"),
        status="UNPAID",
    )
    db.add(receivable)
    db.commit()

    with pytest.raises(HTTPException) as error:
        customer_payment_api.create_customer_payment(
            CustomerPaymentCreate(
                account_receivable_id=receivable.id,
                payment_date=date(2026, 8, 21),
                amount=Decimal("101.00"),
                payment_method="BANK_TRANSFER",
            ),
            db,
            SimpleNamespace(id=1),
        )

    assert error.value.status_code == 400
    assert receivable.received_amount == Decimal("0.00")
    assert receivable.outstanding_amount == Decimal("100.00")
