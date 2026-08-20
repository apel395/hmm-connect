from decimal import Decimal

from app.services.financial_reconciliation_service import FinancialReconciliationService


def test_reconciliation_status_zero_difference():
    row = FinancialReconciliationService._row(
        "ACCOUNTS_PAYABLE",
        Decimal("55500.00"),
        Decimal("55500.00"),
        [],
    )
    assert row["difference"] == Decimal("0.00")
    assert row["status"] == "RECONCILED"


def test_reconciliation_status_out_of_balance():
    row = FinancialReconciliationService._row(
        "INVENTORY",
        Decimal("500000.00"),
        Decimal("285000.00"),
        [],
    )
    assert row["difference"] == Decimal("215000.00")
    assert row["status"] == "OUT_OF_BALANCE"


def test_reconciliation_status_not_configured():
    row = FinancialReconciliationService._row(
        "ACCOUNTS_RECEIVABLE",
        Decimal("100000.00"),
        Decimal("0.00"),
        [],
        configured=False,
    )
    assert row["difference"] == Decimal("100000.00")
    assert row["status"] == "NOT_CONFIGURED"
