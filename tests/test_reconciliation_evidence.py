from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.accounting_posting_rule import AccountingPostingRule
from app.models.accounting_setting import AccountingSetting
from app.models.chart_of_account import ChartOfAccount
from app.models.goods_receipt import GoodsReceipt, GoodsReceiptItem
from app.models.inventory import Inventory
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.opening_balance import OpeningBalance
from app.models.payment import Payment
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.supplier_invoice import SupplierInvoice, SupplierInvoiceLine
from app.models.warehouse import Warehouse
from app.services.financial_reconciliation_service import FinancialReconciliationService


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()
    engine.dispose()


def account(db, code, name, kind="ASSET"):
    row = ChartOfAccount(account_number=code, account_name=name,
                         account_type=kind,
                         normal_balance="CREDIT" if kind == "LIABILITY" else "DEBIT",
                         is_active=True, is_posting=True)
    db.add(row)
    db.flush()
    return row


def journal(db, number, account_id, *, debit="0", credit="0",
            reference_type="TEST", reference_id=1, day=20):
    row = JournalEntry(journal_number=number, posting_date=date(2026, 9, day),
                       status="POSTED", reference_type=reference_type,
                       reference_id=reference_id)
    row.lines.append(JournalLine(account_id=account_id,
                                 debit=Decimal(debit), credit=Decimal(credit)))
    db.add(row)


def test_subcent_average_is_not_unmapped_inventory(db):
    food = account(db, "100-300-100", "Food")
    warehouse = Warehouse(code="WH-005", name="Warehouse")
    product = Product(code="BEEF", name="Beef", group_code="1", group_name="Food",
                      subgroup_code="1", subgroup_name="Food", uom="KG",
                      usage_uom="KG", inventory_account_id=food.id)
    db.add_all([warehouse, product])
    db.flush()
    db.add(Inventory(product_id=product.id, warehouse_id=warehouse.id,
                     quantity=Decimal("243.1100"), average_cost=Decimal("140612.4388")))
    journal(db, "INV-POSTED", food.id, debit="34184290.00")
    db.commit()

    row = FinancialReconciliationService(db).inventory()
    assert row["source_balance"] == row["gl_balance"] == Decimal("34184290.00")
    assert row["variance_breakdown"]["unmapped_stock"] == Decimal("0.00")
    assert row["status"] == "RECONCILED"


def test_real_unmapped_stock_remains_visible(db):
    food = account(db, "100-300-100", "Food")
    warehouse = Warehouse(code="WH-005", name="Warehouse")
    product = Product(code="UNKNOWN", name="Unknown", group_code="1", group_name="Food",
                      subgroup_code="1", subgroup_name="Food", uom="PCS", usage_uom="PCS")
    db.add_all([warehouse, product])
    db.flush()
    db.add(Inventory(product_id=product.id, warehouse_id=warehouse.id,
                     quantity=Decimal("1"), average_cost=Decimal("25")))
    db.commit()
    row = FinancialReconciliationService(db).inventory()
    assert row["variance_breakdown"]["unmapped_stock"] == Decimal("25.00")
    assert row["status"] == "OUT_OF_BALANCE"


def test_suspense_compares_posted_receipt_less_posted_matched_invoice(db):
    suspense = account(db, "200-100-999", "AP Suspense", "LIABILITY")
    db.add(AccountingSetting(setting_key="AP_SUSPENSE_ACCOUNT", account_id=suspense.id))
    warehouse = Warehouse(code="WH-005", name="Warehouse")
    product = Product(code="FOOD", name="Food", group_code="1", group_name="Food",
                      subgroup_code="1", subgroup_name="Food", uom="PCS", usage_uom="PCS",
                      tax_category="NON_TAXABLE", inventory_treatment="STOCK")
    db.add_all([warehouse, product])
    db.flush()
    receipt = GoodsReceipt(receipt_number="GR-2026-1", status="POSTED",
                           destination_type="WAREHOUSE", warehouse_id=warehouse.id,
                           received_at=datetime(2026, 1, 6, tzinfo=timezone.utc))
    item = GoodsReceiptItem(product_id=product.id, quantity=Decimal("10"),
                            unit_cost=Decimal("12"))
    receipt.items.append(item)
    db.add(receipt)
    db.flush()
    journal(db, "GR-J", suspense.id, credit="120",
            reference_type="GOODS_RECEIPT", reference_id=receipt.id)
    db.commit()

    service = FinancialReconciliationService(db)
    pending = service.clearing_suspense()
    assert pending["source_balance"] == pending["gl_balance"] == Decimal("120")
    assert pending["status"] == "OPEN_ITEMS"
    assert pending["receipt_evidence"][0]["receipt_number"] == "GR-2026-1"

    draft = SupplierInvoice(internal_invoice_number="INV-DRAFT", supplier_invoice_number="EXT-DRAFT",
                            supplier_id=1, invoice_date=date(2026, 9, 20),
                            subtotal=Decimal("60"), total_amount=Decimal("60"), status="DRAFT")
    draft.lines.append(SupplierInvoiceLine(
        description="Not yet posted", product_id=product.id, goods_receipt_item_id=item.id,
        quantity=Decimal("5"), unit_price=Decimal("12"), line_amount=Decimal("60")))
    db.add(draft)
    db.commit()
    still_pending = service.clearing_suspense()
    assert still_pending["source_balance"] == Decimal("120")
    assert still_pending["receipt_evidence"][0]["invoice_numbers"] == []
    draft.status = "VOID"
    db.commit()

    invoice = SupplierInvoice(internal_invoice_number="INV-2026-1",
                              supplier_invoice_number="EXT-1", supplier_id=1,
                              invoice_date=date(2026, 9, 21), subtotal=Decimal("60"),
                              total_amount=Decimal("60"), status="POSTED")
    invoice.lines.append(SupplierInvoiceLine(
        description="Matched food", product_id=product.id, goods_receipt_item_id=item.id,
        quantity=Decimal("5"), unit_price=Decimal("12"), line_amount=Decimal("60")))
    db.add(invoice)
    db.flush()
    journal(db, "SI-J", suspense.id, debit="60",
            reference_type="SUPPLIER_INVOICE", reference_id=invoice.id, day=21)
    db.commit()

    earlier = service.clearing_suspense(as_of=date(2026, 9, 20))
    assert earlier["source_balance"] == earlier["gl_balance"] == Decimal("120")
    current = service.clearing_suspense()
    assert current["source_balance"] == current["gl_balance"] == Decimal("60")
    assert current["receipt_evidence"][0]["invoice_numbers"] == ["INV-2026-1"]
    assert current["receipt_evidence"][0]["invoiced_amount"] == Decimal("60")
    assert current["receipt_evidence"][0]["invoice_net_amount"] == Decimal("60")
    assert current["receipt_evidence"][0]["items"][0]["outstanding_quantity"] == Decimal("5")
    assert current["status"] == "OPEN_ITEMS"

    final_invoice = SupplierInvoice(internal_invoice_number="INV-2026-2",
                                    supplier_invoice_number="EXT-2", supplier_id=1,
                                    invoice_date=date(2026, 9, 22), subtotal=Decimal("60"),
                                    total_amount=Decimal("60"), status="POSTED")
    final_invoice.lines.append(SupplierInvoiceLine(
        description="Remaining food", product_id=product.id, goods_receipt_item_id=item.id,
        quantity=Decimal("5"), unit_price=Decimal("12"), line_amount=Decimal("60")))
    db.add(final_invoice)
    db.flush()
    journal(db, "SI-J-2", suspense.id, debit="60",
            reference_type="SUPPLIER_INVOICE", reference_id=final_invoice.id, day=22)
    db.commit()

    cleared = service.clearing_suspense()
    assert cleared["source_balance"] == cleared["gl_balance"] == Decimal("0")
    assert cleared["status"] == "RECONCILED"
    assert cleared["receipt_evidence"] == []
    assert cleared["price_variance_evidence"] == []


def test_fully_invoiced_price_difference_remains_visible_in_suspense_gl(db):
    suspense = account(db, "200-100-999", "AP Suspense", "LIABILITY")
    db.add(AccountingSetting(setting_key="AP_SUSPENSE_ACCOUNT", account_id=suspense.id))
    warehouse = Warehouse(code="WH-PRICE", name="Warehouse")
    product = Product(code="FOOD-PRICE", name="Food", group_code="1", group_name="Food",
                      subgroup_code="1", subgroup_name="Food", uom="PCS", usage_uom="PCS")
    db.add_all([warehouse, product])
    db.flush()
    receipt = GoodsReceipt(receipt_number="GR-PRICE", status="POSTED",
                           destination_type="WAREHOUSE", warehouse_id=warehouse.id,
                           received_at=datetime(2026, 9, 20, tzinfo=timezone.utc))
    item = GoodsReceiptItem(product_id=product.id, quantity=Decimal("10"), unit_cost=Decimal("12"))
    receipt.items.append(item)
    db.add(receipt)
    db.flush()
    journal(db, "GR-PRICE-J", suspense.id, credit="120",
            reference_type="GOODS_RECEIPT", reference_id=receipt.id)
    invoice = SupplierInvoice(internal_invoice_number="INV-PRICE", supplier_invoice_number="EXT-PRICE",
                              supplier_id=1, invoice_date=date(2026, 9, 21), subtotal=Decimal("140"),
                              total_amount=Decimal("140"), status="POSTED")
    invoice.lines.append(SupplierInvoiceLine(
        description="Food", product_id=product.id, goods_receipt_item_id=item.id,
        quantity=Decimal("10"), unit_price=Decimal("14"), line_amount=Decimal("140")))
    db.add(invoice)
    db.flush()
    journal(db, "INV-PRICE-J", suspense.id, debit="140",
            reference_type="SUPPLIER_INVOICE", reference_id=invoice.id, day=21)
    db.commit()

    row = FinancialReconciliationService(db).clearing_suspense()
    assert row["source_balance"] == Decimal("0")
    assert row["gl_balance"] == Decimal("-20")
    assert row["status"] == "OUT_OF_BALANCE"
    assert row["receipt_evidence"] == []
    assert row["price_variance_evidence"][0]["price_difference"] == Decimal("20")


@pytest.mark.parametrize(("invoice_price", "invoice_total"), [
    ("14", "70"),
    ("10", "50"),
])
def test_invoice_journal_debits_suspense_and_credits_payable_without_extra_setup(
    db, monkeypatch, invoice_price, invoice_total,
):
    import app.services.supplier_invoice_service as invoice_module
    from app.services.supplier_invoice_service import SupplierInvoiceService

    suspense = account(db, "200-100-999", "AP Suspense", "LIABILITY")
    payable = account(db, "200-100-1", "Trade AP", "LIABILITY")
    db.add_all([
        AccountingSetting(setting_key="AP_SUSPENSE_ACCOUNT", account_id=suspense.id),
        AccountingSetting(setting_key="ACCOUNTS_PAYABLE_ACCOUNT", account_id=payable.id),
    ])
    supplier = Supplier(code="SUP-V", name="Supplier", is_active=True)
    warehouse = Warehouse(code="WH-V", name="Warehouse")
    product = Product(code="ITEM-V", name="Item", group_code="1", group_name="Group",
                      subgroup_code="1", subgroup_name="Group", uom="PCS", usage_uom="PCS")
    db.add_all([supplier, warehouse, product])
    db.flush()
    receipt = GoodsReceipt(receipt_number="GR-V", supplier_id=supplier.id,
                           destination_type="WAREHOUSE", warehouse_id=warehouse.id,
                           received_at=datetime(2026, 9, 20, tzinfo=timezone.utc), status="POSTED")
    item = GoodsReceiptItem(product_id=product.id, quantity=Decimal("10"), unit_cost=Decimal("12"))
    receipt.items.append(item)
    db.add(receipt)
    db.flush()
    journal(db, "GR-V-J", suspense.id, credit="120",
            reference_type="GOODS_RECEIPT", reference_id=receipt.id)
    invoice = SupplierInvoice(internal_invoice_number="INV-V", supplier_invoice_number="EXT-V",
                              supplier_id=supplier.id, invoice_date=date(2026, 9, 21),
                              subtotal=Decimal(invoice_total), total_amount=Decimal(invoice_total), status="VERIFIED")
    invoice.lines.append(SupplierInvoiceLine(description="Item", product_id=product.id,
        goods_receipt_item_id=item.id, quantity=Decimal("5"), unit_price=Decimal(invoice_price),
        line_amount=Decimal(invoice_total)))
    db.add(invoice)
    db.flush()
    monkeypatch.setattr(invoice_module, "next_document_number", lambda *_a, **_kw: "JV-V")
    monkeypatch.setattr(invoice_module, "record_audit", lambda *_a, **_kw: None)
    service = SupplierInvoiceService(db)
    monkeypatch.setattr(service, "_ensure_invoice_location", lambda _invoice: None)

    receipt_journal = db.query(JournalEntry).filter(JournalEntry.journal_number == "GR-V-J").one()
    receipt_journal.status = "DRAFT"
    with pytest.raises(HTTPException, match="Post receiving journal"):
        service.generate_journal(invoice, type("User", (), {"id": 1})(), commit=False)
    receipt_journal.status = "POSTED"

    created = service.generate_journal(invoice, type("User", (), {"id": 1})(), commit=False)
    amounts = {line.account_id: (Decimal(line.debit), Decimal(line.credit)) for line in created.lines}
    assert amounts[suspense.id] == (Decimal(invoice_total), Decimal("0"))
    assert amounts[payable.id] == (Decimal("0"), Decimal(invoice_total))
    assert len(amounts) == 2


def test_ap_bridge_exposes_orphan_payment_and_manual_opening(db):
    stock = account(db, "100-300-100", "Food")
    payable = account(db, "200-100-1", "Trade AP", "LIABILITY")
    db.add(AccountingPostingRule(event_type="SUPPLIER_INVOICE_INVENTORY",
                                 debit_account_id=stock.id, credit_account_id=payable.id,
                                 is_active=True))
    supplier = Supplier(code="SUP-1", name="Supplier", is_active=True)
    db.add(supplier)
    db.flush()
    invoice = SupplierInvoice(internal_invoice_number="INV-2026-1",
                              supplier_invoice_number="EXT-1", supplier_id=supplier.id,
                              invoice_date=date(2026, 9, 20), subtotal=Decimal("100"),
                              total_amount=Decimal("100"), status="POSTED")
    invoice.lines.append(SupplierInvoiceLine(description="Food", quantity=Decimal("1"),
                                             unit_price=Decimal("100"), line_amount=Decimal("100")))
    payment = Payment(payment_number="PAY-2026-1", payment_date=date(2026, 9, 20),
                      amount=Decimal("20"), payment_method="BANK",
                      status="POSTED", supplier_id=supplier.id, created_by_id=1)
    db.add_all([invoice, payment])
    db.flush()
    journal(db, "SI-AP", payable.id, credit="100",
            reference_type="SUPPLIER_INVOICE", reference_id=invoice.id)
    journal(db, "PAY-AP", payable.id, debit="20",
            reference_type="SUPPLIER_PAYMENT", reference_id=payment.id)
    db.add(OpeningBalance(fiscal_year=2026, account_id=payable.id,
                          amount=Decimal("30"), balance_type="CREDIT"))
    db.commit()

    row = FinancialReconciliationService(db).accounts_payable()
    assert row["source_balance"] == Decimal("100")
    assert row["gl_balance"] == Decimal("110")
    assert row["difference"] == Decimal("-10")
    evidence = {entry["kind"]: entry for entry in row["ap_documents"]}
    assert evidence["PAYMENT"]["difference"] == Decimal("20")
    assert evidence["PAYMENT"]["source_amount"] == Decimal("0")
    assert evidence["OPENING_GL"]["source_amount"] is None
    assert evidence["OPENING_GL"]["difference"] == Decimal("-30")
    assert row["ap_document_summary"]["document_difference_total"] == row["difference"]
    assert row["ap_document_summary"]["opening_gl"] == Decimal("30")
