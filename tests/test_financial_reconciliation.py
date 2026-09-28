from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.account_receivable import AccountReceivable
from app.models.accounting_posting_rule import AccountingPostingRule
from app.models.chart_of_account import ChartOfAccount
from app.models.inventory import Inventory
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.supplier_invoice import SupplierInvoice, SupplierInvoiceLine
from app.models.warehouse import Warehouse
from app.api.v1.financial_reconciliation import _access, router
from app.services.financial_reconciliation_service import FinancialReconciliationService


@pytest.fixture
def reconciliation_db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    yield db
    db.close()


def account(db, number, name, normal_balance):
    row = ChartOfAccount(
        account_number=number,
        account_name=name,
        account_type="LIABILITY" if normal_balance == "CREDIT" else "ASSET",
        normal_balance=normal_balance,
        is_posting=True,
        is_active=True,
    )
    db.add(row)
    db.flush()
    return row


def rule(db, event_type, debit_account, credit_account):
    db.add(AccountingPostingRule(
        event_type=event_type,
        debit_account_id=debit_account.id,
        credit_account_id=credit_account.id,
        is_active=True,
    ))


def journal(db, number, account_row, *, debit="0", credit="0", status="POSTED"):
    entry = JournalEntry(
        journal_number=number,
        posting_date=date(2026, 8, 20),
        status=status,
        reference_type="TEST",
        reference_id=1,
    )
    entry.lines.append(JournalLine(
        account_id=account_row.id,
        debit=Decimal(debit),
        credit=Decimal(credit),
    ))
    db.add(entry)


def supplier_invoice(db, supplier, number, *, status="POSTED", balance="1000000"):
    row = SupplierInvoice(
        internal_invoice_number=number,
        supplier_invoice_number=f"EXT-{number}",
        supplier_id=supplier.id,
        invoice_date=date(2026, 8, 20),
        subtotal=Decimal("1000000"),
        total_amount=Decimal("1000000"),
        paid_amount=Decimal("1000000") - Decimal(balance),
        balance_amount=Decimal(balance),
        status=status,
    )
    row.lines.append(SupplierInvoiceLine(
        description="Reconciliation fixture",
        quantity=Decimal("1"),
        unit_price=Decimal("1000000"),
        line_amount=Decimal("1000000"),
    ))
    db.add(row)
    return row


@pytest.fixture
def ap_setup(reconciliation_db):
    db = reconciliation_db
    inventory_account = account(db, "1100", "Inventory", "DEBIT")
    expense_account = account(db, "5100", "Direct Use", "DEBIT")
    payable_account = account(db, "2100", "Accounts Payable", "CREDIT")
    supplier = Supplier(code="SUP-1", name="Supplier", is_active=True)
    db.add(supplier)
    db.flush()
    rule(db, "SUPPLIER_INVOICE_INVENTORY", inventory_account, payable_account)
    rule(db, "SUPPLIER_INVOICE_DIRECT_USE", expense_account, payable_account)
    return db, supplier, payable_account


@pytest.mark.parametrize(("balance", "gl_credit"), [
    ("1000000", "1000000"),
    ("600000", "600000"),
    ("0", "0"),
])
def test_ap_reconciles_posted_invoice_remaining_balance(ap_setup, balance, gl_credit):
    db, supplier, payable = ap_setup
    supplier_invoice(db, supplier, f"INV-{balance}", balance=balance)
    journal(db, f"JE-{balance}", payable, credit=gl_credit)
    db.commit()

    row = FinancialReconciliationService(db).accounts_payable()

    assert row["source_balance"] == Decimal(balance)
    assert row["gl_balance"] == Decimal(gl_credit)
    assert row["difference"] == Decimal("0")
    assert row["status"] == "RECONCILED"
    assert len(row["accounts"]) == 1  # both invoice rules use the same AP account


def test_ap_exposes_difference_and_ignores_unrecognized_invoices(ap_setup):
    db, supplier, payable = ap_setup
    supplier_invoice(db, supplier, "POSTED", balance="1000000")
    for status in ("DRAFT", "VERIFIED", "REJECTED", "VOID"):
        supplier_invoice(db, supplier, status, status=status, balance="250000")
    journal(db, "JE-POSTED", payable, credit="900000")
    journal(db, "JE-DRAFT", payable, credit="100000", status="DRAFT")
    journal(db, "JE-VOID", payable, credit="100000", status="VOID")
    db.commit()

    row = FinancialReconciliationService(db).accounts_payable()

    assert row["source_balance"] == Decimal("1000000")
    assert row["gl_balance"] == Decimal("900000")
    assert row["difference"] == Decimal("100000")
    assert row["status"] == "OUT_OF_BALANCE"


def test_ap_missing_posting_rule_is_not_configured(reconciliation_db):
    row = FinancialReconciliationService(reconciliation_db).accounts_payable()
    assert row["status"] == "NOT_CONFIGURED"
    assert row["accounts"] == []


def inventory_setup(db, *, quantity, average_cost, gl_balance):
    inventory_account = account(db, "1100", "Inventory", "DEBIT")
    payable_account = account(db, "2100", "Accounts Payable", "CREDIT")
    rule(db, "SUPPLIER_INVOICE_INVENTORY", inventory_account, payable_account)
    product = Product(
        code="P-1", name="Product", group_code="1", group_name="Group",
        subgroup_code="1-1", subgroup_name="Subgroup", uom="PCS",
        usage_uom="PCS", is_active=True,
    )
    warehouse = Warehouse(code="WH-1", name="Warehouse", is_active=True)
    db.add_all([product, warehouse])
    db.flush()
    db.add(Inventory(
        product_id=product.id,
        warehouse_id=warehouse.id,
        quantity=Decimal(quantity),
        average_cost=Decimal(average_cost),
    ))
    journal(db, "JE-INV", inventory_account, debit=gl_balance)
    db.commit()


@pytest.mark.parametrize(("quantity", "average_cost", "gl_balance", "expected_drift"), [
    ("100", "10000", "1000000", Decimal("1000000.00")),
    ("78.5", "10000", "1000000", Decimal("785000.00")),
])
def test_inventory_valuation_against_posted_gl(
    reconciliation_db, quantity, average_cost, gl_balance, expected_drift,
):
    inventory_setup(
        reconciliation_db,
        quantity=quantity,
        average_cost=average_cost,
        gl_balance=gl_balance,
    )
    row = FinancialReconciliationService(reconciliation_db).inventory()
    assert row["difference"] == Decimal("-1000000.00")
    assert row["variance_breakdown"]["valuation_method"] == expected_drift
    assert row["status"] == "OUT_OF_BALANCE"


def test_inventory_missing_posting_rule_is_not_configured(reconciliation_db):
    row = FinancialReconciliationService(reconciliation_db).inventory()
    assert row["status"] == "NOT_CONFIGURED"


def test_ar_is_not_configured_without_canonical_posting_rule(reconciliation_db):
    db = reconciliation_db
    # An AR row alone is not authority to guess a GL control account.
    from app.models.customer import Customer
    customer = Customer(customer_code="CUS-1", customer_name="Customer", is_active=True)
    db.add(customer)
    db.flush()
    db.add(AccountReceivable(
        invoice_number="AR-1", customer_id=customer.id,
        invoice_date=date(2026, 8, 20), due_date=date(2026, 9, 20),
        amount=Decimal("100000"), received_amount=Decimal("0"),
        outstanding_amount=Decimal("100000"), status="UNPAID",
    ))
    db.commit()
    row = FinancialReconciliationService(db).accounts_receivable()
    assert row["source_balance"] == Decimal("100000")
    assert row["status"] == "NOT_CONFIGURED"
    assert row["accounts"] == []


def test_report_is_read_only_and_contract_is_stable(ap_setup):
    db, supplier, payable = ap_setup
    supplier_invoice(db, supplier, "INV-READ-ONLY")
    journal(db, "JE-READ-ONLY", payable, credit="1000000")
    db.commit()
    tracked = (SupplierInvoice, AccountReceivable, Inventory, JournalEntry, JournalLine)
    before = {model: db.query(model).count() for model in tracked}

    report = FinancialReconciliationService(db).report()

    after = {model: db.query(model).count() for model in tracked}
    assert after == before
    assert not db.new and not db.dirty and not db.deleted
    assert set(report) == {"items", "summary", "scope", "read_only"}
    assert report["scope"] == "CURRENT_BALANCE"
    assert report["read_only"] is True
    assert len(report["items"]) == 4


def test_credit_and_debit_normal_balances_are_respected(reconciliation_db):
    debit_account = account(reconciliation_db, "1100", "Debit", "DEBIT")
    credit_account = account(reconciliation_db, "2100", "Credit", "CREDIT")
    journal(reconciliation_db, "JE-DEBIT", debit_account, debit="120", credit="20")
    journal(reconciliation_db, "JE-CREDIT", credit_account, debit="20", credit="120")
    reconciliation_db.commit()
    assert FinancialReconciliationService(reconciliation_db)._gl_balance(
        [debit_account.id, credit_account.id]
    ) == Decimal("200")


def test_not_configured_status_preserves_observed_difference():
    row = FinancialReconciliationService._row(
        "ACCOUNTS_RECEIVABLE", Decimal("100000"), Decimal("0"), [], configured=False,
    )
    assert row["difference"] == Decimal("100000")
    assert row["status"] == "NOT_CONFIGURED"


@pytest.mark.parametrize("role", [
    "SYSTEM_ADMINISTRATOR", "FINANCE", "GENERAL_MANAGER", "AUDITOR",
])
def test_financial_reconciliation_access_roles(role):
    permissions = [] if role == "SYSTEM_ADMINISTRATOR" else [SimpleNamespace(code="finance.view")]
    _access(SimpleNamespace(roles=[SimpleNamespace(name=role, permissions=permissions)]))


def test_operational_role_is_denied_and_router_is_get_only():
    with pytest.raises(HTTPException) as denied:
        _access(SimpleNamespace(roles=[SimpleNamespace(name="WAREHOUSE", permissions=[])]))
    assert denied.value.status_code == 403
    assert [route.methods for route in router.routes] == [{"GET"}]
