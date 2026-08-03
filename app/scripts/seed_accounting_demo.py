"""Seed a repeatable purchasing-to-accounting development scenario.

Usage:
    python -m app.scripts.seed_accounting_demo
    python -m app.scripts.seed_accounting_demo --with-payment
    python -m app.scripts.seed_accounting_demo --reset
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import or_

from app.api.v1 import journals, payments
from app.core.database import SessionLocal
from app.models.accounting_posting_rule import AccountingPostingRule
from app.models.chart_of_account import ChartOfAccount
from app.models.department import Department
from app.models.general_ledger import GeneralLedger
from app.models.goods_receipt import GoodsReceipt
from app.models.inventory import Inventory
from app.models.journal_entry import JournalEntry
from app.models.location import Location
from app.models.payment import Payment
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_requisition import PurchaseRequisition
from app.models.stock_movement import StockMovement
from app.models.supplier import Supplier
from app.models.supplier_invoice import SupplierInvoice
from app.models.user import User
from app.models.warehouse import Warehouse
from app.schemas.goods_receipt import GoodsReceiptCreate, GoodsReceiptItemCreate
from app.schemas.payment import PaymentAllocationInput, PaymentCreate
from app.schemas.purchase_order import PurchaseOrderCreate, PurchaseOrderItemCreate
from app.schemas.purchase_requisition import PurchaseRequisitionCreate, PurchaseRequisitionItemCreate
from app.schemas.supplier_invoice import SupplierInvoiceInput, SupplierInvoiceLineInput
from app.services.goods_receipt_service import GoodsReceiptService
from app.services.purchase_order_service import PurchaseOrderService
from app.services.purchase_requisition_service import PurchaseRequisitionService
from app.services.supplier_invoice_service import SupplierInvoiceService

MARKER = "HMM_ACCOUNTING_DEMO_V1"
PR_NUMBER = "PR-DEV-0001"
PO_NUMBER = "PO-DEV-0001"
GR_NUMBER = "GR-DEV-0001"
PAYMENT_NUMBER = "PAY-DEV-0001"
INVOICE_NUMBERS = ("INV-DEV-0001", "INV-DEV-0002", "INV-DEV-0003")
ZERO = Decimal("0")


def actor(db, role: str) -> User:
    user = db.query(User).join(User.roles).filter_by(name=role).first()
    if user:
        return user
    user = db.query(User).join(User.roles).filter_by(name="ADMIN").first()
    if user:
        return user
    raise RuntimeError(f"Seed requires an existing {role} or ADMIN user")


def upsert(db, model, lookup: dict, values: dict):
    row = db.query(model).filter_by(**lookup).first()
    if row is None:
        row = model(**lookup, **values)
        db.add(row)
        db.flush()
    else:
        for key, value in values.items():
            setattr(row, key, value)
    return row


def ensure_masters(db):
    location = upsert(db, Location, {"code": "DEV-PKU"}, {"name": "Development Pekanbaru", "location_type": "OFFICE", "is_active": True})
    purchasing = upsert(db, Department, {"code": "DEV-PUR"}, {"name": "Development Purchasing", "is_active": True})
    finance = upsert(db, Department, {"code": "DEV-FIN"}, {"name": "Development Finance", "is_active": True})
    warehouse = upsert(db, Warehouse, {"code": "DEV-WH-01"}, {"name": "Development Warehouse 01", "address": "Pekanbaru development warehouse", "is_active": True})
    supplier = upsert(db, Supplier, {"code": "DEV-SUP-001"}, {"name": "PT Supplier Demo HMM", "address": "Pekanbaru", "is_active": True})
    product_specs = (
        ("DEV-ITEM-001", "Cleaning Chemical", "LTR", Decimal("150000")),
        ("DEV-ITEM-002", "Mineral Water", "CTN", Decimal("30000")),
        ("DEV-ITEM-003", "Office Paper", "REAM", Decimal("100000")),
    )
    products = []
    for code, name, uom, cost in product_specs:
        products.append(upsert(db, Product, {"code": code}, {
            "name": name, "group_code": "DEV", "group_name": "Development Items",
            "subgroup_code": "DEMO", "subgroup_name": "Accounting Demo", "uom": uom,
            "usage_uom": uom, "conversion": Decimal("1"), "description": MARKER,
            "cost_price": cost, "selling_price": ZERO, "is_active": True,
        }))
    account_specs = (
        ("110100", "Bank", "ASSET", "DEBIT"),
        ("120100", "Inventory Asset", "ASSET", "DEBIT"),
        ("130100", "Accounts Receivable", "ASSET", "DEBIT"),
        ("200100", "Accounts Payable", "LIABILITY", "CREDIT"),
        ("210100", "Goods Received Not Invoiced", "LIABILITY", "CREDIT"),
        ("510100", "Housekeeping Supplies Expense", "EXPENSE", "DEBIT"),
        ("510200", "Office Supplies Expense", "EXPENSE", "DEBIT"),
    )
    created_accounts = {}
    for number, name, kind, normal in account_specs:
        created_accounts[number] = upsert(db, ChartOfAccount, {"account_number": number}, {
            "account_name": name, "account_type": kind, "normal_balance": normal,
            "description": MARKER, "is_posting": True, "is_system": False, "is_active": True,
        })

    def compatible(number: str, kind: str, name: str):
        exact = db.query(ChartOfAccount).filter_by(account_number=number).first()
        if exact:
            return exact
        return db.query(ChartOfAccount).filter(
            ChartOfAccount.account_type == kind,
            ChartOfAccount.is_posting.is_(True), ChartOfAccount.is_active.is_(True),
            ChartOfAccount.account_name.ilike(f"%{name}%"),
        ).first()

    bank = compatible("110100", "ASSET", "bank") or created_accounts["110100"]
    inventory = compatible("120100", "ASSET", "inventory") or created_accounts["120100"]
    payable = compatible("200100", "LIABILITY", "payable") or created_accounts["200100"]
    expense = compatible("510100", "EXPENSE", "supplies") or created_accounts["510100"]
    rules = {
        "SUPPLIER_INVOICE_INVENTORY": (inventory, payable),
        "SUPPLIER_INVOICE_DIRECT_USE": (expense, payable),
        "SUPPLIER_PAYMENT": (payable, bank),
    }
    finance_user = actor(db, "FINANCE")
    for event, (debit, credit) in rules.items():
        rule = db.query(AccountingPostingRule).filter_by(event_type=event, is_active=True).first()
        if rule is None:
            db.add(AccountingPostingRule(event_type=event, debit_account_id=debit.id, credit_account_id=credit.id, description=f"{MARKER}: {event}", is_active=True, created_by_id=finance_user.id))
        else:
            # Preserve a compatible active configuration; only repair invalid mappings.
            if not rule.debit_account or not rule.debit_account.is_active or not rule.debit_account.is_posting:
                rule.debit_account_id = debit.id
            if not rule.credit_account or not rule.credit_account.is_active or not rule.credit_account.is_posting:
                rule.credit_account_id = credit.id
    db.commit()
    return location, purchasing, finance, warehouse, supplier, products, bank


def reset(db):
    payments_to_delete = db.query(Payment).filter(or_(Payment.payment_number == PAYMENT_NUMBER, Payment.notes.ilike(f"%{MARKER}%"))).all()
    invoices = db.query(SupplierInvoice).filter(SupplierInvoice.supplier_invoice_number.in_(INVOICE_NUMBERS)).all()
    payment_ids = [row.id for row in payments_to_delete]
    invoice_ids = [row.id for row in invoices]
    journals_to_delete = db.query(JournalEntry).filter(or_(
        (JournalEntry.reference_type == "SUPPLIER_PAYMENT") & JournalEntry.reference_id.in_(payment_ids or [-1]),
        (JournalEntry.reference_type == "SUPPLIER_INVOICE") & JournalEntry.reference_id.in_(invoice_ids or [-1]),
    )).all()
    for journal in journals_to_delete:
        db.query(GeneralLedger).filter_by(reference_number=journal.journal_number).delete(synchronize_session=False)
    for row in payments_to_delete:
        db.delete(row)
    for row in journals_to_delete:
        db.delete(row)
    for row in invoices:
        db.delete(row)
    db.flush()

    receipt = db.query(GoodsReceipt).filter_by(receipt_number=GR_NUMBER).first()
    if receipt:
        movements = db.query(StockMovement).filter_by(goods_receipt_id=receipt.id).all()
        for movement in movements:
            inventory = db.query(Inventory).filter_by(product_id=movement.product_id, warehouse_id=movement.warehouse_id).first()
            if inventory:
                inventory.quantity = max(ZERO, Decimal(inventory.quantity) - Decimal(movement.quantity))
                if inventory.quantity == ZERO:
                    inventory.average_cost = ZERO
            db.delete(movement)
        db.delete(receipt)
    po = db.query(PurchaseOrder).filter_by(po_number=PO_NUMBER).first()
    if po:
        db.delete(po)
    pr = db.query(PurchaseRequisition).filter_by(pr_number=PR_NUMBER).first()
    if pr:
        db.delete(pr)
    db.commit()
    print("Reset accounting demo documents; shared master data and append-only audit history were preserved.")


def seed_documents(db, location, purchasing, warehouse, supplier, products):
    requester = actor(db, "REQUESTER")
    warehouse_user = actor(db, "WAREHOUSE")
    finance_user = actor(db, "FINANCE")
    quantities = (Decimal("20"), Decimal("100"), Decimal("30"))
    prices = (Decimal("150000"), Decimal("30000"), Decimal("100000"))
    pr = db.query(PurchaseRequisition).filter_by(pr_number=PR_NUMBER).first()
    if pr is None:
        pr = PurchaseRequisitionService.create(db, data=PurchaseRequisitionCreate(
            request_date=date.today(), source_type="HISTORICAL_IMPORT", external_reference=MARKER,
            notes=f"{MARKER}: approved purchasing sample",
            items=[PurchaseRequisitionItemCreate(product_id=p.id, quantity=q, estimated_price=price) for p, q, price in zip(products, quantities, prices)],
        ), current_user=requester)
        pr.pr_number = PR_NUMBER; pr.status = "APPROVED"; db.commit(); db.refresh(pr)
    po = db.query(PurchaseOrder).filter_by(po_number=PO_NUMBER).first()
    if po is None:
        po = PurchaseOrderService.create(db, data=PurchaseOrderCreate(
            supplier_id=supplier.id, department_id=purchasing.id, location_id=location.id,
            order_date=date.today(), source_type="HISTORICAL_IMPORT", external_reference=MARKER,
            expected_date=date.today(), notes=f"{MARKER}: approved order",
            purchase_requisition_ids=[pr.id],
            items=[PurchaseOrderItemCreate(purchase_requisition_item_id=line.id, quantity=q, unit_price=price) for line, q, price in zip(pr.items, quantities, prices)],
        ), user=requester)
        po.po_number = PO_NUMBER; po.status = "APPROVED"; pr.status = "CONVERTED"; db.commit(); db.refresh(po)
    receipt = db.query(GoodsReceipt).filter_by(receipt_number=GR_NUMBER).first()
    if receipt is None:
        receipt = GoodsReceiptService.create(db, data=GoodsReceiptCreate(
            purchase_order_id=po.id, source_type="HISTORICAL_IMPORT", external_reference=MARKER,
            destination_type="WAREHOUSE", warehouse_id=warehouse.id,
            notes=f"{MARKER}: full warehouse receipt",
            items=[GoodsReceiptItemCreate(purchase_order_item_id=line.id, quantity=line.quantity) for line in po.items],
        ), user=warehouse_user)
        receipt.receipt_number = GR_NUMBER; db.commit(); db.refresh(receipt)
        receipt = GoodsReceiptService.post(db, receipt_id=receipt.id, user=warehouse_user)

    invoice_totals = (Decimal("4000000"), Decimal("3000000"), Decimal("2000000"))
    invoice_products = (products[0], products[1], products[2])
    service = SupplierInvoiceService(db)
    invoices = []
    for supplier_number, total, product, po_item, gr_item in zip(INVOICE_NUMBERS, invoice_totals, invoice_products, po.items, receipt.items):
        invoice = db.query(SupplierInvoice).filter_by(supplier_id=supplier.id, supplier_invoice_number=supplier_number).first()
        if invoice is None:
            invoice = service.create(SupplierInvoiceInput(
                supplier_invoice_number=supplier_number, supplier_id=supplier.id, invoice_date=date.today(),
                received_date=date.today(), due_date=date.today(), purchase_order_id=po.id,
                goods_receipt_id=receipt.id, department_id=purchasing.id, location_id=location.id,
                currency="IDR", total_amount=total, notes=f"{MARKER}: {supplier_number}", source_type="HISTORICAL_IMPORT",
                lines=[SupplierInvoiceLineInput(product_id=product.id, purchase_order_item_id=po_item.id,
                    goods_receipt_item_id=gr_item.id, description=product.name, quantity=Decimal("1"),
                    uom=product.uom, unit_price=total, department_id=purchasing.id)],
            ), finance_user)
            invoice.internal_invoice_number = supplier_number; db.commit(); db.refresh(invoice)
            invoice = service.verify(invoice, finance_user)
            journal = service.generate_journal(invoice, finance_user)
            journals.post(journal.id, db, finance_user)
            db.refresh(invoice)
        invoices.append(invoice)
    return pr, po, receipt, invoices, finance_user


def create_and_post_payment(db, supplier, bank, invoices, finance_user):
    existing = db.query(Payment).filter_by(payment_number=PAYMENT_NUMBER).first()
    if existing:
        return existing
    amounts = (Decimal("4000000"), Decimal("2000000"), Decimal("500000"))
    payload = PaymentCreate(
        supplier_id=supplier.id, payment_date=date.today(), payment_method="BANK_TRANSFER",
        payment_account_id=bank.id, currency="IDR", total_amount=Decimal("6500000"),
        reference_number=MARKER, notes=f"{MARKER}: multiple-invoice payment",
        allocations=[PaymentAllocationInput(supplier_invoice_id=invoice.id, allocated_amount=amount) for invoice, amount in zip(invoices, amounts)],
    )
    result = payments.create(payload, db, finance_user)
    payment = db.get(Payment, result["id"]); payment.payment_number = PAYMENT_NUMBER; db.commit()
    payments.approve(payment.id, db, finance_user)
    payments.generate(payment.id, db, finance_user)
    payments.post(payment.id, db, finance_user)
    return db.get(Payment, payment.id)


def summary(db, supplier, invoices, payment=None):
    for invoice in invoices:
        db.refresh(invoice)
    eligible = payments.eligible(supplier.id, "IDR", db, actor(db, "FINANCE"))
    print(f"Supplier: {supplier.code} - {supplier.name}")
    print(f"Eligible invoices: {len(eligible)}; outstanding: {sum((Decimal(str(x['outstanding_balance'])) for x in eligible), ZERO)}")
    for invoice in invoices:
        print(f"Invoice: {invoice.internal_invoice_number}; status={invoice.status}; payment_status={invoice.payment_status}; paid={invoice.paid_amount}; balance={invoice.balance_amount}")
    if payment:
        print(f"Payment: {payment.payment_number}; status={payment.status}; journal={payment.journal_entry.journal_number}")
        print("Allocations: " + ", ".join(f"{a.supplier_invoice.internal_invoice_number}={a.allocated_amount}" for a in payment.allocations))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="Remove only demo documents and reverse their receipt inventory")
    parser.add_argument("--with-payment", action="store_true", help="Create, approve, journal, and post the demo payment")
    args = parser.parse_args()
    db = SessionLocal()
    try:
        if args.reset:
            reset(db)
            return
        location, purchasing, _finance, warehouse, supplier, products, bank = ensure_masters(db)
        pr, po, receipt, invoices, finance_user = seed_documents(db, location, purchasing, warehouse, supplier, products)
        payment = create_and_post_payment(db, supplier, bank, invoices, finance_user) if args.with_payment else None
        print(f"Documents: {pr.pr_number}, {po.po_number}, {receipt.receipt_number}")
        summary(db, supplier, invoices, payment)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
