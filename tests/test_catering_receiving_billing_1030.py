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
    assert invoice.status == "VERIFIED"
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
