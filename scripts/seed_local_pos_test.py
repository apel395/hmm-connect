"""Minimal isolated POS demo data. Refuses all databases except hmm_pos_test.

Run interactively after bootstrap, inside docker-compose.pos-local.yml's API:
    python scripts/seed_local_pos_test.py
"""

from getpass import getpass

from sqlalchemy import text

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import Base  # noqa: F401 - import all registered models
from app.models.accounting_setting import AccountingSetting
from app.models.business_unit import BusinessUnit
from app.models.chart_of_account import ChartOfAccount
from app.models.customer import Customer
from app.models.department import Department
from app.models.location import Location
from app.models.location_department import LocationDepartment
from app.models.product import Product
from app.models.role import Role
from app.models.user import User


def ensure(db, model, lookup, values):
    row = db.query(model).filter_by(**lookup).one_or_none()
    if row is None:
        row = model(**lookup, **values)
        db.add(row)
        db.flush()
    return row


def main():
    db = SessionLocal()
    try:
        actual_database = db.execute(text("SELECT current_database()")).scalar_one()
        if actual_database != "hmm_pos_test":
            raise SystemExit("REFUSED: this script only runs against hmm_pos_test")

        role = ensure(db, Role, {"name": "SYSTEM_ADMINISTRATOR"}, {"description": "Local POS test administrator"})
        admin = db.query(User).filter_by(username="postest").one_or_none()
        if admin is None:
            password = getpass("Choose a LOCAL test password for user postest: ")
            if len(password) < 8:
                raise SystemExit("Password must have at least 8 characters")
            admin = User(username="postest", email="postest@example.invalid", full_name="Local POS Tester",
                         password_hash=hash_password(password), is_active=True)
            db.add(admin)
        if role not in admin.roles:
            admin.roles.append(role)

        unit = ensure(db, BusinessUnit, {"code": "POS-TEST"}, {"name": "Catering POS Test", "is_active": True})
        location = ensure(db, Location, {"code": "POS-TEST-PKU"}, {
            "name": "POS Test Pekanbaru", "location_type": "OPERATIONS", "business_unit_id": unit.id, "is_active": True})
        department = ensure(db, Department, {"code": "POS-TEST-OUTLET"}, {
            "name": "POS Test Outlet", "business_unit_id": unit.id, "is_active": True})
        ensure(db, LocationDepartment, {"location_id": location.id, "department_id": department.id}, {})

        accounts = {}
        for code, name, account_type, normal in (
            ("400-110-901", "Local POS Sales Revenue", "REVENUE", "CREDIT"),
            ("100-100-901", "Local POS Cash", "ASSET", "DEBIT"),
            ("100-200-101", "Piutang Usaha - Local Test", "ASSET", "DEBIT"),
        ):
            accounts[code] = ensure(db, ChartOfAccount, {"account_number": code}, {
                "account_name": name, "account_type": account_type, "normal_balance": normal,
                "is_active": True, "is_posting": True, "account_subtype": "CASH" if code == "100-100-901" else "OTHER"})
        for key, account in (
            ("POS_CASH_ACCOUNT", accounts["100-100-901"]),
            ("POS_CARD_ACCOUNT", accounts["100-100-901"]),
            ("POS_TRANSFER_ACCOUNT", accounts["100-100-901"]),
            ("POS_SALES_REVENUE_ACCOUNT", accounts["400-110-901"]),
            ("ACCOUNTS_RECEIVABLE_ACCOUNT", accounts["100-200-101"]),
        ):
            ensure(db, AccountingSetting, {"setting_key": key}, {"account_id": account.id})

        for code, name, price in (
            ("POS-TST-001", "Test Nasi Box", 35000),
            ("POS-TST-002", "Test Kopi", 18000),
        ):
            ensure(db, Product, {"code": code}, {
                "name": name, "group_code": "5", "group_name": "POS Test Menus",
                "subgroup_code": "", "subgroup_name": "", "uom": "PORSI", "usage_uom": "PORSI",
                "conversion": 1, "item_type": "SELL", "inventory_treatment": "NON_STOCK",
                "catalog_type": "CATERING", "selling_price": price,
                "sales_business_unit_id": unit.id, "sales_location_id": location.id,
                "tax_category": "NON_TAXABLE", "is_taxable": False, "tax_rate": 0,
                "service_charge_rate": 0, "pbjt_rate": 0, "is_active": True})

        ensure(db, Customer, {"customer_code": "POS-TEST-CUST"}, {
            "customer_name": "POS Sample Customer", "is_active": True})
        db.commit()
        print("Local POS demo ready. Login at http://localhost:5173 as postest.")
        print("Open /pos for test menus and /pos/sales for saved drafts.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
