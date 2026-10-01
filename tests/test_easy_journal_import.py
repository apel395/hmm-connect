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
    db.flush()

    assert list(groups) == ["GROUP:1", "GROUP:2"]
    first_group = groups["GROUP:1"]
    assert len(first_group) == 2
    continuation = first_group[1].normalized_data_json
    assert continuation["posting_date"] == "2026-01-15"
    assert continuation["description"] == "First journal"
    assert continuation["location_code"] == "BTM"
    assert first_group[0].document_number == "JIMP-TEST-G0001"
    assert first_group[1].document_number == "JIMP-TEST-G0001"
