"""Catering Receiving supplier billing and invoice handoff."""
from datetime import date
from decimal import Decimal
import pytest
from fastapi import HTTPException

from app.models.chart_of_account import ChartOfAccount
from app.models.accounting_setting import AccountingSetting
from app.models.journal_entry import JournalEntry
from app.models.supplier_invoice import SupplierInvoice
from app.services.goods_receipt_service import GoodsReceiptService
from test_receiving_line_destinations import setup_receiving, create
from test_stock_opname_functional import stock_db


def _setup(stock_db):
    data = setup_receiving(stock_db)
    db, warehouse, user, products, balances, expense, supplier = data
    payable = ChartOfAccount(account_number="200-101-1030",account_name="Catering payable",
                             account_type="LIABILITY",normal_balance="CREDIT",
                             is_posting=True,is_active=True)
    discount_account = ChartOfAccount(account_number="410-990-1030",account_name="Purchase discount",
        account_type="EXPENSE",normal_balance="CREDIT",is_posting=True,is_active=True)
    db.add_all([payable, discount_account]);db.flush()
    db.add(AccountingSetting(setting_key="PURCHASE_DISCOUNT_ACCOUNT",account_id=discount_account.id))
    supplier.payable_account_id = payable.id
    db.commit()
    return data


def test_complete_receiving_documents_auto_verify_invoice_and_charge_once(stock_db):
    data = _setup(stock_db)
    db, warehouse, user, products, balances, expense, supplier = data
    for product in products: product.catalog_type = "CATERING"
    db.commit()
    receipt = create(data)
    receipt.supplier_invoice_number = "VENDOR-CAT-1030"
    receipt.supplier_invoice_date = GoodsReceiptService.business_date(receipt.received_at)
    receipt.supplier_invoice_due_date = receipt.supplier_invoice_date
    receipt.discount_amount = Decimal("1.00")
    receipt.shipping_fee_amount = Decimal("3.00")
    receipt.admin_fee_amount = Decimal("2.00")
    receipt.other_fee_amount = Decimal("1.00")
    receipt.shipping_fee_account_id = expense.id
    receipt.admin_fee_account_id = expense.id
    receipt.other_fee_account_id = expense.id
    receipt.other_fee_description = "Packing materials"
    receipt.supplier_document_total = receipt.subtotal + receipt.tax_amount - 1 + 3 + 2 + 1
    db.commit()

    posted = GoodsReceiptService.post(db,receipt_id=receipt.id,user=user)
    invoice = db.query(SupplierInvoice).filter_by(goods_receipt_id=receipt.id).one()
    assert posted.status == "POSTED"
    assert invoice.status == "VERIFIED", (
        f"receipt={posted.receipt_number} source={posted.source_type!r}"
        f" doc_ref={posted.supplier_invoice_number!r} doc_date={posted.supplier_invoice_date!r}"
        f" document_total={posted.supplier_document_total!r} receipt_total={posted.total_amount!r}"
        f" invoice_total={invoice.total_amount!r} invoice_ref={invoice.supplier_invoice_number!r}"
        f" invoice_date={invoice.invoice_date!r} invoice_status={invoice.status!r}"
        f" receipt_fees={(posted.shipping_fee_amount,posted.admin_fee_amount,posted.other_fee_amount)!r}"
        f" invoice_fees={(invoice.shipping_fee_amount,invoice.admin_fee_amount,invoice.other_fee_amount)!r}"
        f" receipt_discount={posted.discount_amount!r} invoice_discount={invoice.discount_amount!r}"
    )
    assert invoice.supplier_invoice_number == "VENDOR-CAT-1030"
    assert invoice.total_amount == invoice.subtotal + invoice.tax_amount - 1 + 3 + 2 + 1
    journal = db.query(JournalEntry).filter_by(reference_type="SUPPLIER_INVOICE",reference_id=invoice.id).one()
    assert journal.status == "DRAFT"
    assert sum(Decimal(x.debit or 0) for x in journal.lines) == sum(Decimal(x.credit or 0) for x in journal.lines)
    assert sum(Decimal(x.debit or 0) for x in journal.lines if x.account_id == expense.id) >= 6


def test_missing_vendor_reference_does_not_auto_verify(stock_db):
    data = _setup(stock_db)
    db, warehouse, user, products, balances, expense, supplier = data
    receipt = create(data)
    GoodsReceiptService.post(db,receipt_id=receipt.id,user=user)
    invoice = db.query(SupplierInvoice).filter_by(goods_receipt_id=receipt.id).one()
    assert invoice.status == "DRAFT"
    assert invoice.supplier_invoice_number.startswith("PENDING-")


def test_fee_requires_explicit_expense_account(stock_db):
    data = _setup(stock_db)
    db, warehouse, user, products, balances, expense, supplier = data
    receipt = create(data)
    receipt.shipping_fee_amount = Decimal("10")
    receipt.shipping_fee_account_id = None
    db.commit()
    with pytest.raises(HTTPException,match="Shipping fee requires an active"):
        GoodsReceiptService.post(db,receipt_id=receipt.id,user=user)


def test_wrong_supplier_document_total_keeps_invoice_draft(stock_db):
    data = _setup(stock_db)
    db, warehouse, user, products, balances, expense, supplier = data
    products[0].catalog_type = "CATERING"
    db.commit()
    receipt = create(data, items=[dict(product_id=products[0].id, quantity=2, unit_cost=10)])
    receipt.supplier_invoice_number = "VENDOR-MISMATCH-1030"
    receipt.supplier_invoice_date = GoodsReceiptService.business_date(receipt.received_at)
    receipt.supplier_document_total = Decimal("21.00")
    db.commit()
    GoodsReceiptService.post(db, receipt_id=receipt.id, user=user)
    invoice = db.query(SupplierInvoice).filter_by(goods_receipt_id=receipt.id).one()
    assert invoice.total_amount == Decimal("20.00")
    assert invoice.status == "DRAFT"
    assert db.query(JournalEntry).filter_by(reference_type="SUPPLIER_INVOICE", reference_id=invoice.id).count() == 0


def test_non_pkp_vat_invoice_does_not_block_physical_receiving(stock_db):
    data = _setup(stock_db)
    db, warehouse, user, products, balances, expense, supplier = data
    products[0].catalog_type = "CATERING"
    supplier.is_pkp = False
    db.commit()
    receipt = create(data, items=[dict(product_id=products[0].id, quantity=2,
                                     unit_cost=10, is_taxable=True, tax_rate=11)])
    receipt.supplier_invoice_number = "VENDOR-NON-PKP-1030"
    receipt.supplier_invoice_date = GoodsReceiptService.business_date(receipt.received_at)
    receipt.tax_invoice_number = "FAKTUR-1030"
    receipt.tax_invoice_date = receipt.supplier_invoice_date
    receipt.supplier_document_total = Decimal("22.20")
    db.commit()
    result = GoodsReceiptService.post(db, receipt_id=receipt.id, user=user)
    invoice = db.query(SupplierInvoice).filter_by(goods_receipt_id=receipt.id).one()
    assert result.status == "POSTED"
    assert invoice.tax_amount == Decimal("2.20")
    assert invoice.status == "DRAFT"


def test_tax_snapshot_flush_preserves_supplier_fee_total(stock_db):
    data = _setup(stock_db)
    db, warehouse, user, products, balances, expense, supplier = data
    receipt = create(data, items=[dict(product_id=products[0].id, quantity=2, unit_cost=10)])
    receipt.discount_amount = Decimal("1.00")
    receipt.shipping_fee_amount = Decimal("3.00")
    receipt.shipping_fee_account_id = expense.id
    GoodsReceiptService._recalculate_totals(receipt, db)
    assert receipt.total_amount == Decimal("22.00")
    db.flush()
    assert receipt.total_amount == Decimal("22.00"), "Tax snapshot flush must preserve supplier adjustments"


def test_closed_invoice_period_leaves_supplier_draft_without_blocking_receipt(stock_db):
    data = _setup(stock_db)
    db, warehouse, user, products, balances, expense, supplier = data
    products[0].catalog_type = "CATERING"
    db.commit()
    receipt = create(data, items=[dict(product_id=products[0].id, quantity=2, unit_cost=10)])
    receipt.supplier_invoice_number = "VENDOR-OLD-DATE-1030"
    receipt.supplier_invoice_date = date(2026, 1, 2)
    receipt.supplier_document_total = Decimal("20.00")
    db.commit()
    result = GoodsReceiptService.post(db, receipt_id=receipt.id, user=user)
    invoice = db.query(SupplierInvoice).filter_by(goods_receipt_id=receipt.id).one()
    assert result.status == "POSTED"
    assert invoice.invoice_date == date(2026, 1, 2)
    assert invoice.status == "DRAFT"
