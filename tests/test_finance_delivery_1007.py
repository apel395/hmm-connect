from datetime import date, datetime, timezone
from decimal import Decimal as D
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.business_unit import BusinessUnit
from app.models.location import Location
from app.models.department import Department
from app.models.location_department import LocationDepartment
from app.models.chart_of_account import ChartOfAccount
from app.models.fiscal_period import FiscalPeriod
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.general_ledger import GeneralLedger
from app.models.opening_balance import OpeningBalance
from app.models.goods_receipt import GoodsReceipt
from app.models.supplier import Supplier
from app.models.supplier_invoice import SupplierInvoice, SupplierInvoiceLine
from app.models.bank_account import BankAccount
from app.models.payment import Payment
from app.schemas.journal import JournalCreate
from app.schemas.payment import PaymentCreate
from app.api.v1 import journals, cashier, payments, financial_reports
from app.services.management_dashboard import build_dashboard
from app.services.sales_transaction_service import SalesTransactionService
from app.models.sales_transaction import SalesTransactionLine

ADMIN = SimpleNamespace(id=1, full_name="Test", username="test", roles=[SimpleNamespace(name="SYSTEM_ADMINISTRATOR")], default_location_id=None, location_id=None)


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    unit = BusinessUnit(code="U", name="Unit")
    session.add(unit); session.flush()
    location = Location(code="L", name="Location", business_unit_id=unit.id)
    department = Department(code="OPS", name="Operations", business_unit_id=unit.id)
    session.add_all([location, department]); session.flush()
    session.add(LocationDepartment(location_id=location.id, department_id=department.id))
    session.add(FiscalPeriod(fiscal_year=2026, fiscal_month=1, period_name="January", start_date=date(2026,1,1), end_date=date(2026,1,31), is_open=True, is_closed=False, allow_backdated_entries=True))
    accounts = []
    for code, kind, normal, subtype, group in [("400", "REVENUE", "CREDIT", None, "OPERATING_REVENUE"), ("700-1", "EXPENSE", "DEBIT", None, "OPERATING_EXPENSE"), ("100-1", "ASSET", "DEBIT", "PETTY_CASH", "CURRENT_ASSET"), ("200-1", "LIABILITY", "CREDIT", None, "CURRENT_LIABILITY")]:
        account = ChartOfAccount(account_number=code, account_name=code, account_type=kind, normal_balance=normal, account_subtype=subtype, financial_statement_group=group, is_active=True, is_posting=True)
        session.add(account); accounts.append(account)
    session.commit()
    for module in (journals, cashier, payments):
        monkeypatch.setattr(module, "record_audit", lambda *a, **kw: None)
    yield session, unit, location, department, accounts
    session.close(); engine.dispose()


def test_manual_single_line_posts_real_difference_without_contra(db):
    s, unit, location, _, a = db
    entry = journals.create(JournalCreate(posting_date=date(2026,1,5), document_type="MANUAL_JOURNAL", document_number="T", reference_type="MANUAL", reference_id=0, location_id=location.id, business_unit_id=unit.id, lines=[dict(account_id=a[2].id, debit="100", credit="0")]), s, ADMIN)
    assert entry["allowed_actions"]["can_post"]
    result = journals.post(entry["id"], s, ADMIN)
    assert result["difference"] == D("100")
    assert s.query(JournalLine).count() == 1
    assert s.query(GeneralLedger).count() == 1
    assert s.query(OpeningBalance).count() == 0


def test_source_journal_still_rejects_unbalanced_post(db):
    s, unit, location, _, a = db
    j = JournalEntry(journal_number="SOURCE", status="DRAFT", posting_date=date(2026,1,5), reference_type="GOODS_RECEIPT", reference_id=0, location_id=location.id, business_unit_id=unit.id)
    j.lines = [JournalLine(account_id=a[2].id, debit=100, credit=0, location_id=location.id, business_unit_id=unit.id)]
    s.add(j); s.flush()
    with pytest.raises(HTTPException): journals.post_locked_journal(s, journal=j, user=ADMIN)
    assert s.query(GeneralLedger).count() == 0


def test_cashier_posts_once_and_dashboard_matches_department_and_opening(db):
    s, unit, location, department, a = db
    s.add(OpeningBalance(fiscal_year=2026, account_id=a[2].id, location_id=location.id, amount=D("500"), balance_type="DEBIT")); s.commit()
    data = cashier.CashEntry(posting_date=date(2026,1,5), operation="PAYMENT", cash_account_id=a[2].id, counterpart_account_id=a[1].id, amount="30", location_id=location.id, business_unit_id=unit.id, department_id=department.id, reference_number="V-1", description="Lunch")
    created = cashier.create(data, s, ADMIN)
    assert s.query(GeneralLedger).count() == 0
    cashier.post(created["id"], s, ADMIN)
    cashier.post(created["id"], s, ADMIN)
    assert s.query(GeneralLedger).count() == 2
    report = build_dashboard(s, year=2026, month=1, location_id=location.id)
    assert report["MTD"]["nop"] == D("-30")
    assert report["position"]["ASSETS"] == D("470")
    assert report["balance_gap"] == D("500")
    assert report["departments"][0]["YTD"]["nop"] == D("-30")
    assert s.query(OpeningBalance).one().amount == D("500")
    other_location = build_dashboard(s, year=2026, month=1, location_id=99)
    assert other_location["YTD"]["nop"] == 0
    period = s.query(FiscalPeriod).one(); period.is_open = False; period.is_closed = True; s.commit()
    with pytest.raises(HTTPException): cashier.create(data, s, ADMIN)


@pytest.mark.parametrize("short_over", ["2", "-2"])
def test_payment_fees_post_without_changing_invoice_tax_or_ap_allocation(db, short_over):
    s, unit, location, _, a = db
    supplier = Supplier(code="SUP", name="Supplier", payable_account_id=a[3].id)
    s.add(supplier); s.flush()
    receipt = GoodsReceipt(receipt_number="GR-1", received_at=datetime(2026,1,2,tzinfo=timezone.utc), supplier_id=supplier.id, location_id=location.id, business_unit_id=unit.id, status="POSTED", destination_type="DIRECT_USE", received_by_id=1)
    s.add(receipt); s.flush()
    invoice = SupplierInvoice(internal_invoice_number="INV-TEST", supplier_invoice_number="SUP-1", goods_receipt_id=receipt.id, supplier_id=supplier.id, invoice_date=date(2026,1,2), subtotal=D("90"), tax_amount=D("10"), total_amount=D("100"), balance_amount=D("100"), status="POSTED", business_unit_id=unit.id, location_id=location.id)
    invoice.lines = [SupplierInvoiceLine(quantity=1, unit_price=90, line_amount=90, tax_amount=10, tax_rate=D("11.1111"), is_taxable=True, uom="Pcs", description="Test item")]
    bank = BankAccount(bank_name="Cash", account_name="Cash", account_number="1", currency="IDR", business_unit_id=unit.id, coa_account_id=a[2].id, is_payment_account=True)
    s.add_all([invoice, bank]); s.commit()
    amount = D("100") + D("10") + D(short_over)
    payload = PaymentCreate(supplier_id=supplier.id, payment_date=date(2026,1,5), total_amount="100", bank_charge_amount="10", bank_charge_account_id=a[1].id, short_over_amount=short_over, short_over_account_id=a[1].id, difference_reason="Bank fees and rounding", allocations=[dict(supplier_invoice_id=invoice.id, allocated_amount="100")], funding_lines=[dict(bank_account_id=bank.id, amount=amount)])
    created = payments.create(payload, s, ADMIN)
    payments.approve(created["id"], s, ADMIN)
    generated = payments.generate(created["id"], s, ADMIN)
    payment = s.get(Payment, created["id"])
    journals.post(payment.journal_entry_id, s, ADMIN)
    assert generated["expected_funding"] == amount
    assert invoice.total_amount == D("100") and invoice.tax_amount == D("10")
    assert invoice.paid_amount == D("100")
    assert sum(l.debit - l.credit for l in payment.journal_entry.lines) == 0
    assert sum(l.debit for l in payment.journal_entry.lines if l.account_id == a[3].id) == D("100")
    assert sum(l.credit for l in payment.journal_entry.lines if l.account_id == a[2].id) == amount


def test_service_charge_is_snapshot_and_included_in_totals():
    line = SalesTransactionLine(quantity=1, unit_price=100, line_amount=100, tax_amount=10, service_charge_rate=5, service_charge_amount=5)
    totals = SalesTransactionService._totals([line], D("0"))
    assert totals["subtotal"] == 100 and totals["tax_amount"] == 10
    assert totals["service_charge_amount"] == 5 and totals["total"] == 115


def test_detail_print_overrides_kap_default(db):
    from app.models.financial_report_setting import FinancialReportSetting
    from app.services.financial_reporting_service import FinancialReportingService
    s, _, _, _, _ = db
    s.add(FinancialReportSetting(report_type="BALANCE_SHEET", header_only=True)); s.commit()
    assert FinancialReportingService(s).build(report_type="BALANCE_SHEET", as_of_date=date(2026,1,31), detail=True)["header_only"] is False


def test_client_invoice_layout_preserves_ar_amounts_and_rejects_unscoped_legacy_access(db, monkeypatch):
    from app.api.v1 import ar_invoice_print
    from app.models.customer import Customer
    from app.models.account_receivable import AccountReceivable
    s, _, location, _, _ = db
    monkeypatch.setattr(ar_invoice_print, "record_audit", lambda *a, **kw: None)
    customer = Customer(customer_code="C-1", customer_name="Client", address="Client address")
    s.add(customer); s.flush()
    ar = AccountReceivable(invoice_number="AR-1", customer_id=customer.id, invoice_date=date(2026,1,5), due_date=date(2026,1,31), amount=100, received_amount=20, outstanding_amount=80)
    s.add(ar); s.commit()
    ar_invoice_print.update_layout(customer.id, ar_invoice_print.InvoiceLayout(title="BILL", footer="Client footer"), s, ADMIN)
    result = ar_invoice_print.invoice(ar.id, s, ADMIN)
    assert result["layout"]["title"] == "BILL"
    assert result["amount"] == 100 and result["received_amount"] == 20 and result["outstanding_amount"] == 80
    assert s.query(JournalEntry).count() == 0
    scoped = SimpleNamespace(roles=[], default_location_id=location.id, location_id=location.id)
    with pytest.raises(HTTPException) as error:
        ar_invoice_print.invoice(ar.id, s, scoped)
    assert error.value.status_code == 403
