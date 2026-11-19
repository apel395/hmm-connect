"""Synthetic AR revenue recap tests; no customer financial data committed to GitHub."""
from datetime import datetime
from decimal import Decimal
from io import BytesIO

import pytest
from openpyxl import Workbook

from app.services.ar_import_staging import decimal_value, parse_catering_workbook, source_date


def workbook_bytes(rows):
    wb = Workbook()
    sh = wb.active
    sh.title = "Sheet1"
    sh.cell(5, 2, "LOKASI")
    sh.cell(5, 3, "TANGGAL INVOICE")
    sh.cell(5, 4, "DECRIPTION")
    for month in range(12):
        for delta, heading in enumerate(("DPP", "PB-1", "TOTAL")):
            sh.cell(6, 5 + month * 3 + delta, heading)
    sh.cell(6, 43, "Jumlah")
    sh.cell(6, 44, "Sisa Aging")
    for n, row in enumerate(rows, 8):
        sh.cell(n, 2, row.get("location", "RUMIN"))
        if row.get("date") is not None:
            sh.cell(n, 3, row["date"])
        sh.cell(n, 4, row.get("number", f"INV-{n}"))
        sh.cell(n, 5, row.get("dpp", 100))
        sh.cell(n, 6, row.get("pb1", 10))
        sh.cell(n, 7, row.get("gross", 110))
        sh.cell(n, 41, row.get("ar", 110))
        if row.get("paid_date"):
            sh.cell(n, 42, row["paid_date"])
        sh.cell(n, 43, row.get("paid", 0))
        sh.cell(n, 44, row.get("aging", 110))
        sh.cell(n, 45, row.get("remark", ""))
    sh.cell(8 + len(rows), 1, "TOTAL")
    output = BytesIO()
    wb.save(output)
    wb.close()
    return output.getvalue()


def codes(row):
    return {problem["code"] for problem in row["issues"]}


def test_extracts_catering_invoice_and_holds_missing_customer_and_due_date():
    rows = parse_catering_workbook(workbook_bytes([{
        "location": "PHM", "number": "PAYROLL-PHM", "date": datetime(2026, 1, 2),
        "paid_date": datetime(2026, 2, 3),
        "paid": 107.8, "aging": 2.2, "remark": "PPH 23",
    }]))
    assert len(rows) == 1
    row = rows[0]
    assert row["source_row"] == 8
    assert row["invoice_number"] == "PAYROLL-PHM"
    assert row["revenue_month"] == 1
    assert row["gross"] == "110"
    assert row["receipt"] == "107.8"
    assert row["pph23_estimate"] == "2.00"
    assert row["business_unit_code"] == "002"
    # PHM is an active catering location in production, but this isolated
    # parser fixture deliberately has no connected master DB.
    assert "UNKNOWN_LOCATION" in codes(row)
    assert "CUSTOMER_MAPPING_REQUIRED" in codes(row)
    assert "DUE_DATE_REQUIRED" in codes(row)
    assert "RECEIPT_BANK_RECONCILIATION" in codes(row)
    assert "WITHHOLDING_DIFFERENCE" not in codes(row)


def test_duplicate_external_invoice_number_blocks_both_rows():
    rows = parse_catering_workbook(workbook_bytes([
        {"number": "SAME-INV", "date": datetime(2026, 1, 10)},
        {"number": "same-inv", "date": datetime(2026, 1, 11)},
    ]))
    assert len(rows) == 2
    assert all("DUPLICATE_NUMBER_IN_FILE" in codes(row) for row in rows)


def test_issues_are_isolated_per_invoice():
    rows = parse_catering_workbook(workbook_bytes([
        {"number": "OK-1", "date": datetime(2026, 1, 10)},
        {"number": "BAD-DATE", "date": None},
        {"number": "BAD-TOTAL", "date": datetime(2026, 1, 11), "gross": 200, "ar": 200, "aging": 200},
    ]))
    assert len(rows) == 3
    assert "MISSING_DATE" not in codes(rows[0])
    assert "MISSING_DATE" in codes(rows[1])
    assert "DPP_PB1_TOTAL_MISMATCH" in codes(rows[2])


def test_rejects_wrong_layout_instead_of_guessing_columns():
    wb = Workbook()
    output = BytesIO()
    wb.save(output)
    with pytest.raises(ValueError, match="Expected revenue recap headers"):
        parse_catering_workbook(output.getvalue())


def test_excel_number_date_and_decimal_precision():
    assert source_date(46024).isoformat() == "2026-01-02"
    assert decimal_value("1.234.567,89") == Decimal("1234567.89")
    assert decimal_value("1,234,567.89") == Decimal("1234567.89")


def test_staging_creates_only_import_rows_and_no_financial_entries():
    import asyncio
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from starlette.datastructures import UploadFile

    from app.models import Base
    from app.models.account_receivable import AccountReceivable
    from app.models.business_unit import BusinessUnit
    from app.models.department import Department
    from app.models.general_ledger import GeneralLedger
    from app.models.import_batch import ImportBatch, ImportRow
    from app.models.journal_entry import JournalEntry
    from app.models.location import Location
    from app.models.location_department import LocationDepartment
    from app.models.sales_transaction import SalesTransaction
    from app.models.user import User
    from app.api.v1.ar_imports import stage

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        unit = BusinessUnit(code="002", name="Project Catering", is_active=True)
        db.add(unit)
        db.flush()
        loc = Location(code="005", name="Rumin", business_unit_id=unit.id, is_active=True)
        dept = Department(code="01", name="Operasional", business_unit_id=unit.id, is_active=True)
        user = User(username="ar-stage-test", email="ar-stage@example.test",
                    full_name="Test User", password_hash="x")
        db.add_all([loc, dept, user])
        db.flush()
        db.add(LocationDepartment(location_id=loc.id, department_id=dept.id))
        db.commit()

        payload = workbook_bytes([{"number": "RUMIN-TEST-01", "date": datetime(2026, 1, 2)}])
        result = asyncio.run(stage(
            file=UploadFile(file=BytesIO(payload), filename="recap.xlsx"),
            db=db, user=user,
        ))
        assert result["status"] == "STAGED"
        assert result["total_rows"] == 1
        assert result["imported_rows"] == 0
        assert db.query(ImportBatch).count() == 1
        assert db.query(ImportRow).count() == 1
        assert db.query(AccountReceivable).count() == 0
        assert db.query(SalesTransaction).count() == 0
        assert db.query(JournalEntry).count() == 0
        assert db.query(GeneralLedger).count() == 0

        # Reupload of the same source returns the same batch, no duplication.
        retry = asyncio.run(stage(
            file=UploadFile(file=BytesIO(payload), filename="recap.xlsx"),
            db=db, user=user,
        ))
        assert retry["id"] == result["id"]
        assert db.query(ImportRow).count() == 1
    engine.dispose()
