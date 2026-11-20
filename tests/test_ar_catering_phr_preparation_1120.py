"""PHR Catering AR staging preparation. Accounting rows must remain untouched."""
import asyncio
from datetime import datetime
from io import BytesIO

import pytest
from fastapi import HTTPException
from openpyxl import Workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.datastructures import UploadFile


def fixture_xlsx(source_rows):
    wb = Workbook()
    sheet = wb.active
    sheet.title = "Sheet1"
    sheet.cell(5, 2, "LOKASI")
    sheet.cell(5, 3, "TANGGAL INVOICE")
    sheet.cell(5, 4, "DECRIPTION")
    for month in range(12):
        for offset, label in enumerate(("DPP", "PB-1", "TOTAL")):
            sheet.cell(6, 5 + month * 3 + offset, label)
    sheet.cell(6, 43, "Jumlah")
    sheet.cell(6, 44, "Sisa Aging")
    for row_number, data in enumerate(source_rows, 8):
        sheet.cell(row_number, 2, data.get("location", "RUMIN"))
        if data.get("date"):
            sheet.cell(row_number, 3, data["date"])
        sheet.cell(row_number, 4, data.get("number", f"INV-{row_number}"))
        sheet.cell(row_number, 5, data.get("dpp", 100))
        sheet.cell(row_number, 6, data.get("pb1", 10))
        sheet.cell(row_number, 7, data.get("gross", 110))
        sheet.cell(row_number, 41, data.get("ar", 110))
        sheet.cell(row_number, 43, data.get("receipt", 0))
        sheet.cell(row_number, 44, data.get("aging", 110))
    sheet.cell(8 + len(source_rows), 1, "TOTAL")
    output = BytesIO()
    wb.save(output)
    wb.close()
    return output.getvalue()


def setup_preparation_masters(db):
    from app.models.business_unit import BusinessUnit
    from app.models.department import Department
    from app.models.location import Location
    from app.models.location_department import LocationDepartment
    from app.models.customer import Customer
    from app.models.chart_of_account import ChartOfAccount
    from app.models.user import User

    unit = BusinessUnit(code="002", name="Project Catering", is_active=True)
    db.add(unit)
    db.flush()
    dept = Department(code="01", name="Operasional", business_unit_id=unit.id, is_active=True)
    loc = Location(code="005", name="Rumin", business_unit_id=unit.id, is_active=True)
    customer = Customer(customer_code="POS-PHR-001", customer_name="PHR", is_active=True)
    user = User(username="finance-phr-test", email="finance-phr@example.test", full_name="Finance PHR", password_hash="x")
    accounts = [
        ChartOfAccount(account_number="100-200-101", account_name="Piutang Usaha",
                       account_type="ASSET", normal_balance="DEBIT", is_active=True, is_posting=True),
        ChartOfAccount(account_number="400-110-100", account_name="Pendapatan Project Catering",
                       account_type="REVENUE", normal_balance="CREDIT", is_active=True, is_posting=True),
        ChartOfAccount(account_number="200-400-101", account_name="PB-1 Tax Payable",
                       account_type="LIABILITY", normal_balance="CREDIT", is_active=True, is_posting=True),
    ]
    db.add_all([dept, loc, customer, user, *accounts])
    db.flush()
    db.add(LocationDepartment(location_id=loc.id, department_id=dept.id))
    db.commit()
    return user, customer, accounts


def test_phr_preparation_produces_balanced_preview_and_no_financial_writes():
    from app.models import Base
    from app.models.account_receivable import AccountReceivable
    from app.models.general_ledger import GeneralLedger
    from app.models.journal_entry import JournalEntry
    from app.models.import_batch import ImportRow
    from app.models.customer_payment import CustomerPayment
    from app.models.sales_transaction import SalesTransaction
    from app.api.v1.ar_imports import stage, prepare_staged_batch, get_journal_preview, ARBatchPrepare

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        user, customer, accounts = setup_preparation_masters(db)
        source = fixture_xlsx([
            {"number": "PHR-RUMIN-001", "date": datetime(2026, 1, 2)},
            {"number": "PHR-RUMIN-002", "date": datetime(2026, 1, 3)},
            {"number": "PHR-RUMIN-MISSING-DATE"},
        ])
        staged = asyncio.run(stage(
            file=UploadFile(file=BytesIO(source), filename="phr_recap.xlsx"),
            db=db, user=user,
        ))
        assert staged["total_rows"] == 3
        prepared = prepare_staged_batch(
            staged["id"],
            ARBatchPrepare(
                customer_id=customer.id,
                payment_terms_days=30,
                ar_account_id=accounts[0].id,
                revenue_account_id=accounts[1].id,
                pb1_liability_account_id=accounts[2].id,
                terms_confirmed=True,
                accounts_confirmed=True,
            ),
            db=db, user=user,
        )
        assert prepared["valid_rows"] == 2
        assert prepared["error_rows"] == 1
        preview = get_journal_preview(staged["id"], db=db, user=user)
        assert preview["ready_count"] == 2
        assert preview["blocked_count"] == 1
        assert preview["balanced"] is True
        assert preview["totals"] == {
            "ar_debit": "220.00",
            "revenue_credit": "200.00",
            "pb1_credit": "20.00",
        }
        assert preview["items"][0]["due_date"] == "2026-02-01"
        assert all(item["customer_id"] == customer.id for item in preview["items"])
        assert not preview["posting_enabled"]
        mapped_rows = db.query(ImportRow).order_by(ImportRow.row_number).all()
        assert mapped_rows[0].normalized_data_json["customer_id"] == customer.id
        assert "customer_id" not in mapped_rows[0].raw_data_json
        assert mapped_rows[-1].status == "ERROR"
        for model in (AccountReceivable, SalesTransaction, GeneralLedger, JournalEntry, CustomerPayment):
            assert db.query(model).count() == 0
    engine.dispose()


def test_phr_preparation_requires_explicit_terms_and_valid_account_classes():
    from app.models import Base
    from app.api.v1.ar_imports import stage, prepare_staged_batch, ARBatchPrepare

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        user, customer, accounts = setup_preparation_masters(db)
        staged = asyncio.run(stage(
            file=UploadFile(
                file=BytesIO(fixture_xlsx([{"date": datetime(2026, 2, 1)}])),
                filename="recap.xlsx",
            ), db=db, user=user,
        ))
        valid = dict(customer_id=customer.id, payment_terms_days=15,
                     ar_account_id=accounts[0].id,
                     revenue_account_id=accounts[1].id,
                     pb1_liability_account_id=accounts[2].id,
                     terms_confirmed=True, accounts_confirmed=True)
        for modifications in (
            {"terms_confirmed": False},
            {"accounts_confirmed": False},
            {"customer_id": customer.id + 999},
            {"pb1_liability_account_id": accounts[0].id},
            {"revenue_account_id": accounts[2].id},
        ):
            with pytest.raises(HTTPException):
                prepare_staged_batch(staged["id"], ARBatchPrepare(**{**valid, **modifications}), db=db, user=user)
        prepare_staged_batch(staged["id"], ARBatchPrepare(**valid), db=db, user=user)
        prepare_staged_batch(staged["id"], ARBatchPrepare(**valid), db=db, user=user)
        from app.models.import_batch import ImportRow
        assert db.query(ImportRow).count() == 1
        assert db.query(ImportRow).first().status == "READY"
    engine.dispose()
