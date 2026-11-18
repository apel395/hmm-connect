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


def test_legacy_catering_template_resolves_swapped_location_and_department(db):
    """Old files may contain Operasional as location and PHM as department."""
    from app.models.business_unit import BusinessUnit
    from app.models.department import Department
    from app.models.location import Location
    from app.scripts.journal_import_worker import (
        recover_legacy_dimensions, resolve_business_unit, resolve_line_department,
        resolve_location,
    )
    catering = BusinessUnit(code="002", name="Project Catering", is_active=True)
    db.add(catering)
    db.flush()
    location = Location(code="012", name="PHM", business_unit_id=catering.id, is_active=True)
    department = Department(code="01", name="Operasional", business_unit_id=catering.id, is_active=True)
    db.add_all([location, department])
    db.flush()
    batch = ImportBatch(id=901, batch_number="LEGACY-901", batch_name="Legacy",
                        source="JOURNAL_BULK_IMPORT", import_type="JOURNAL_ENTRY",
                        source_type="JOURNAL_BULK_IMPORT", status="PROCESSING")
    db.add(batch)
    db.flush()
    groups = build_groups(db, batch, [
        (2, "Journal Import", dict(
            document_number="PAYROLL-PHM", posting_date="2026-10-31",
            business_unit_code="Project Catering",
            location_code="Operasional", line_department_code="PHM",
            account_code="600-100-100", debit=100, credit=0,
        )),
        (3, "Journal Import", dict(
            business_unit_code="", location_code="",
            line_department_code="PHM",
            account_code="100-100-100", debit=0, credit=100,
        )),
    ])
    rows = next(iter(groups.values()))
    db.flush()
    assert resolve_location(db, rows[0].normalized_data_json) is None
    assert resolve_line_department(db, rows[0].normalized_data_json) is None
    assert resolve_business_unit(db, rows[0].normalized_data_json, None).id == catering.id

    recover_legacy_dimensions(db, rows)
    db.flush()
    db.expire_all()
    corrected = [db.get(type(row), row.id) for row in rows]
    for row in corrected:
        normalized = row.normalized_data_json
        assert normalized["location_code"] == "012"
        assert normalized["line_department_code"] == "01"
        assert normalized["business_unit_code"] == "002"
        assert "Legacy Excel columns corrected" in normalized["_dimension_mapping_note"]
        assert row.raw_data_json.get("line_department_code") == "PHM"
    assert corrected[0].raw_data_json["location_code"] == "Operasional"


def test_legacy_dimension_recovery_never_crosses_business_units(db):
    from app.models.business_unit import BusinessUnit
    from app.models.department import Department
    from app.models.location import Location
    from app.scripts.journal_import_worker import recover_legacy_dimensions
    catering = BusinessUnit(code="002", name="Project Catering", is_active=True)
    hotel = BusinessUnit(code="001", name="Hotel", is_active=True)
    db.add_all([catering, hotel])
    db.flush()
    db.add_all([
        Location(code="012", name="PHM", business_unit_id=catering.id, is_active=True),
        Department(code="01", name="Operasional", business_unit_id=hotel.id, is_active=True),
    ])
    db.flush()
    batch = ImportBatch(id=902, batch_number="LEGACY-902", batch_name="Mismatch",
                        source="JOURNAL_BULK_IMPORT", import_type="JOURNAL_ENTRY",
                        source_type="JOURNAL_BULK_IMPORT", status="PROCESSING")
    db.add(batch)
    db.flush()
    rows = next(iter(build_groups(db, batch, [(2, "Journal Import", {
        "document_number": "MISMATCH", "posting_date": "2026-10-31",
        "business_unit_code": "Project Catering", "location_code": "Operasional",
        "line_department_code": "PHM", "account_code": "1", "debit": 10,
    })]).values()))
    recover_legacy_dimensions(db, rows)
    assert rows[0].normalized_data_json["location_code"] == "OPERASIONAL"
    assert rows[0].normalized_data_json["line_department_code"] == "PHM"
    assert "_dimension_mapping_note" not in rows[0].normalized_data_json


def test_valid_hotel_dimensions_by_exact_names_are_not_swapped(db):
    from app.models.business_unit import BusinessUnit
    from app.models.department import Department
    from app.models.location import Location
    from app.scripts.journal_import_worker import (
        recover_legacy_dimensions, resolve_business_unit, resolve_line_department,
        resolve_location,
    )
    hotel = BusinessUnit(code="001", name="Hotel", is_active=True)
    db.add(hotel)
    db.flush()
    location = Location(code="009", name="Hotel", business_unit_id=hotel.id, is_active=True)
    department = Department(code="001", name="Front Office", business_unit_id=hotel.id, is_active=True)
    db.add_all([location, department])
    db.flush()
    batch = ImportBatch(id=903, batch_number="HOTEL-903", batch_name="Hotel",
                        source="JOURNAL_BULK_IMPORT", import_type="JOURNAL_ENTRY",
                        source_type="JOURNAL_BULK_IMPORT", status="PROCESSING")
    db.add(batch)
    db.flush()
    rows = next(iter(build_groups(db, batch, [(2, "Journal Import", {
        "document_number": "HOTEL-EXAMPLE", "posting_date": "2026-10-31",
        "business_unit_code": "Hotel", "location_code": "Hotel",
        "line_department_code": "Front Office", "account_code": "1", "debit": 10,
    })]).values()))
    assert resolve_business_unit(db, rows[0].normalized_data_json, None).id == hotel.id
    assert resolve_location(db, rows[0].normalized_data_json).id == location.id
    assert resolve_line_department(db, rows[0].normalized_data_json).id == department.id
    recover_legacy_dimensions(db, rows)
    assert rows[0].normalized_data_json["location_code"] == "HOTEL"
    assert rows[0].normalized_data_json["line_department_code"] == "FRONT OFFICE"
    assert "_dimension_mapping_note" not in rows[0].normalized_data_json
