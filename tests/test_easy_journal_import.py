from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.import_batch import ImportBatch
from app.scripts.journal_import_worker import build_groups, money


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()
    engine.dispose()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1.000.000", Decimal("1000000")),
        ("1,000,000", Decimal("1000000")),
        ("1.000.000,50", Decimal("1000000.50")),
        ("1,000,000.50", Decimal("1000000.50")),
        ("Rp 125.000", Decimal("125000")),
        (125000, Decimal("125000")),
    ],
)
def test_money_accepts_common_excel_and_indonesian_formats(raw, expected):
    assert money(raw, "amount") == expected


def test_journal_group_inherits_blank_header_cells(db):
    batch = ImportBatch(
        id=1,
        batch_number="JIMP-TEST",
        batch_name="Test",
        source="JOURNAL_BULK_IMPORT",
        import_type="JOURNAL_ENTRY",
        source_type="JOURNAL_BULK_IMPORT",
        status="PROCESSING",
    )
    db.add(batch)
    db.flush()

    groups = build_groups(db, batch, [
        (2, "Journal Import", {
            "journal_group": "1",
            "posting_date": "2026-01-15",
            "description": "First journal",
            "location_code": "BTM",
            "account_code": "100-100",
            "debit": "1.000.000",
            "credit": "0",
        }),
        (3, "Journal Import", {
            "journal_group": "",
            "posting_date": "",
            "description": "",
            "location_code": "",
            "account_code": "200-100",
            "debit": "0",
            "credit": "1.000.000",
        }),
        (4, "Journal Import", {
            "journal_group": "2",
            "posting_date": "2026-01-16",
            "description": "Second journal",
            "location_code": "BTM",
            "account_code": "100-100",
            "debit": "500000",
            "credit": "0",
        }),
    ])
    assert list(groups) == ["GROUP:1", "GROUP:2"]
    first_group = groups["GROUP:1"]
    assert len(first_group) == 2
    continuation = first_group[1].normalized_data_json
    assert continuation["posting_date"] == "2026-01-15"
    assert continuation["description"] == "First journal"
    assert continuation["location_code"] == "BTM"
    assert first_group[0].document_number == "JIMP-TEST-G0001"
    assert first_group[1].document_number == "JIMP-TEST-G0001"


def test_document_numbers_group_nonadjacent_lines_without_group_column(db):
    batch = ImportBatch(id=2, batch_number="JIMP-DOC", batch_name="Documents",
                        source="JOURNAL_BULK_IMPORT", import_type="JOURNAL_ENTRY",
                        source_type="JOURNAL_BULK_IMPORT", status="PROCESSING")
    db.add(batch)
    db.flush()
    groups = build_groups(db, batch, [
        (2, "Journal Import", {"document_number": "SALARY-01", "posting_date": "2026-01-31", "description": "Salary", "location_code": "BTM", "account_code": "500", "debit": "100", "credit": "0"}),
        (3, "Journal Import", {"document_number": "RENT-01", "posting_date": "2026-01-30", "description": "Rent", "location_code": "BTM", "account_code": "501", "debit": "200", "credit": "0"}),
        (4, "Journal Import", {"document_number": "SALARY-01", "account_code": "100", "debit": "0", "credit": "100"}),
        (5, "Journal Import", {"document_number": "RENT-01", "account_code": "100", "debit": "0", "credit": "150"}),
        (6, "Journal Import", {"account_code": "100", "debit": "0", "credit": "50"}),
    ])
    assert list(groups) == ["DOCUMENT:SALARY-01", "DOCUMENT:RENT-01"]
    for key, rows in groups.items():
        assert sum(money(row.normalized_data_json["debit"], "debit") for row in rows) == sum(money(row.normalized_data_json["credit"], "credit") for row in rows)
        assert all(row.document_number == key.split(":", 1)[1] for row in rows)
    assert groups["DOCUMENT:SALARY-01"][1].normalized_data_json["posting_date"] == "2026-01-31"
    assert groups["DOCUMENT:RENT-01"][2].normalized_data_json["description"] == "Rent"


def test_eight_lines_four_departments_import_as_one_journal(db, monkeypatch):
    from datetime import date
    from app.models.business_unit import BusinessUnit
    from app.models.location import Location
    from app.models.department import Department
    from app.models.location_department import LocationDepartment
    from app.models.chart_of_account import ChartOfAccount
    from app.models.user import User
    from app.models.role import Role
    from app.models.journal_entry import JournalEntry
    from app.scripts.journal_import_worker import validate_group, import_valid_groups
    unit = BusinessUnit(code="TEST-UNIT", name="Test unit", is_active=True)
    db.add(unit); db.flush()
    location = Location(code="TEST-LOC", name="Test location", business_unit_id=unit.id, is_active=True)
    depts = [Department(code=f"TEST-D{i}", name=f"Department {i}", business_unit_id=unit.id, is_active=True) for i in range(4)]
    user = User(username="test-journal", email="journal@example.test", full_name="Test user", password_hash="x", roles=[Role(name="SYSTEM_ADMINISTRATOR")])
    accounts = [ChartOfAccount(account_number=code, account_name=code, account_type=kind, normal_balance=normal, is_active=True, is_posting=True) for code, kind, normal in [("TEST-EXP", "EXPENSE", "DEBIT"), ("TEST-AP", "LIABILITY", "CREDIT")]]
    db.add_all([location,user,*depts,*accounts]);db.flush()
    db.add_all([LocationDepartment(location_id=location.id,department_id=dept.id) for dept in depts])
    monkeypatch.setattr("app.scripts.journal_import_worker.ActivityService.log", lambda **kwargs: None)
    batch = ImportBatch(id=8,batch_number="TEST-8LINES",batch_name="Test",source="JOURNAL_BULK_IMPORT",import_type="JOURNAL_ENTRY",source_type="JOURNAL_BULK_IMPORT",status="VALIDATED")
    db.add(batch);db.flush()
    raw = []
    # Four debit lines followed by four credits. Adjacency is not a pairing rule.
    for i in range(8):
        raw.append((i+2,"Journal Import",dict(document_number="TEST-REGISTER",posting_date="2026-01-31",description="Test multi-line journal",location_code=location.code,line_department_code=depts[i%4].code,account_code=accounts[0 if i<4 else 1].account_number,debit="25" if i<4 else "0",credit="0" if i<4 else "25")))
    grouped = build_groups(db,batch,raw)
    assert len(grouped) == 1
    lines = next(iter(grouped.values()))
    for index, row in enumerate(lines, 1): row.id = index
    assert validate_group(db,user,batch,lines) == []
    for row in lines: row.status="VALID"
    db.flush()
    import_valid_groups(db,batch,user,False)
    journal = db.query(JournalEntry).one()
    assert journal.posting_date == date(2026,1,31)
    assert journal.department_id is None
    assert len(journal.lines) == 8
    assert [line.department_id for line in journal.lines] == [depts[i%4].id for i in range(8)]
    assert sum(line.debit for line in journal.lines) == sum(line.credit for line in journal.lines) == Decimal("100")


def test_new_line_department_blank_is_not_inherited(db):
    batch = ImportBatch(id=9,batch_number="TEST-BLANK",batch_name="Test",source="JOURNAL_BULK_IMPORT",import_type="JOURNAL_ENTRY",source_type="JOURNAL_BULK_IMPORT",status="PROCESSING")
    db.add(batch);db.flush()
    rows = build_groups(db,batch,[(2,"Journal Import",dict(document_number="TEST-REGISTER",posting_date="2026-01-31",line_department_code="FIRST",account_code="EXP",debit=10)),(3,"Journal Import",dict(line_department_code="",account_code="AP",credit=10))])
    lines=next(iter(rows.values()))
    assert lines[1].normalized_data_json["line_department_code"] == ""
    assert lines[1].normalized_data_json["_line_department_supplied"] is True


def test_template_matches_form_columns_and_dropdown_positions(db):
    from io import BytesIO
    from zipfile import ZipFile
    from xml.etree import ElementTree as ET
    from types import SimpleNamespace
    from app.api.v1.journal_imports import _build_template, TEMPLATE_HEADERS, TEMPLATE_KEYS

    assert TEMPLATE_KEYS == ["posting_date", "document_number", "description", "business_unit_code", "location_code", "line_department_code", "account_code", "line_description", "debit", "credit"]
    assert not any("journal_group" in header for header in TEMPLATE_HEADERS)
    from app.models.business_unit import BusinessUnit
    from app.models.location import Location
    from app.models.department import Department
    from app.models.chart_of_account import ChartOfAccount
    unit = BusinessUnit(code="HOTEL", name="Hotel")
    db.add(unit)
    db.flush()
    db.add_all([Location(code="HOTEL", name="Hotel Location", business_unit_id=unit.id),
                Department(code="FO", name="Front Office", business_unit_id=unit.id),
                ChartOfAccount(account_number="100-100", account_name="Cash", account_type="ASSET", normal_balance="DEBIT", is_posting=True, is_active=True)])
    db.flush()
    payload = _build_template(db, SimpleNamespace(id=1, roles=[], location_id=None, default_location_id=None))
    with ZipFile(BytesIO(payload)) as workbook:
        xml = ET.fromstring(workbook.read("xl/worksheets/sheet2.xml"))
        ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        cells = xml.findall("x:sheetData/x:row", ns)[0].findall("x:c", ns)
        assert len(cells) == 10
        dropdowns = {v.attrib["sqref"]: v.find("x:formula1", ns).text for v in xml.findall("x:dataValidations/x:dataValidation", ns)}
        assert dropdowns == {"D2:D501": "BusinessUnitCodes", "E2:E501": "LocationCodes", "F2:F501": "DepartmentCodes", "G2:G501": "AccountCodes"}
        assert xml.find("x:autoFilter", ns).attrib["ref"] == "A1:J501"
