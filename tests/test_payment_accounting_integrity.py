from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1.payments import validate_payment_journal_integrity


def account(
    account_id,
    account_type,
    normal_balance,
    account_subtype,
    *,
    is_active=True,
    is_posting=True,
):
    return SimpleNamespace(
        id=account_id,
        account_type=account_type,
        normal_balance=normal_balance,
        account_subtype=account_subtype,
        is_active=is_active,
        is_posting=is_posting,
    )


def payment_fixture(bank_credit=Decimal("20000")):
    payable = account(10, "LIABILITY", "CREDIT", "ACCOUNTS_PAYABLE")
    bank = account(20, "ASSET", "DEBIT", "BANK")
    payment = SimpleNamespace(
        id=9,
        supplier=SimpleNamespace(code="SUP-TEST", payable_account_id=payable.id),
        payment_number="PAY-TEST",
        amount=Decimal("20000"),
        business_unit_id=2,
        location_id=3,
        department_id=4,
        funding_lines=[
            SimpleNamespace(
                amount=Decimal("20000"),
                bank_account=SimpleNamespace(coa_account=bank),
            )
        ],
    )
    journal = SimpleNamespace(
        reference_type="SUPPLIER_PAYMENT",
        reference_id=payment.id,
        document_number=payment.payment_number,
        business_unit_id=payment.business_unit_id,
        location_id=payment.location_id,
        department_id=payment.department_id,
        lines=[
            SimpleNamespace(
                account_id=payable.id,
                debit=Decimal("20000"),
                credit=Decimal("0"),
                business_unit_id=2,
                location_id=3,
                department_id=4,
            ),
            SimpleNamespace(
                account_id=bank.id,
                debit=Decimal("0"),
                credit=bank_credit,
                business_unit_id=2,
                location_id=3,
                department_id=4,
            ),
        ],
    )
    db = SimpleNamespace(get=lambda _model, account_id: payable if account_id == payable.id else None)
    return db, payment, journal, payable


def test_payment_journal_matches_direct_supplier_payable_and_selected_bank():
    db, payment, journal, payable = payment_fixture()

    assert validate_payment_journal_integrity(db, payment, journal) is payable


def test_payment_journal_rejects_credit_not_matching_funding():
    db, payment, journal, _ = payment_fixture(bank_credit=Decimal("19000"))

    with pytest.raises(HTTPException) as error:
        validate_payment_journal_integrity(db, payment, journal)

    assert error.value.status_code == 409
    assert "selected funding accounts" in error.value.detail


def test_payment_journal_rejects_wrong_location_dimension():
    db, payment, journal, _ = payment_fixture()
    journal.lines[1].location_id = 99

    with pytest.raises(HTTPException) as error:
        validate_payment_journal_integrity(db, payment, journal)

    assert "dimensions" in error.value.detail
