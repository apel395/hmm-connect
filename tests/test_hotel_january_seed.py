import copy
from datetime import date
import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import BigInteger, create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.business_unit import BusinessUnit
from app.models.chart_of_account import ChartOfAccount
from app.models.department import Department
from app.models.fiscal_period import FiscalPeriod
from app.models.general_ledger import GeneralLedger
from app.models.import_batch import ImportRow
from app.models.journal_entry import JournalEntry
from app.models.location import Location
from app.models.location_department import LocationDepartment
from app.models.role import Role
from app.models.user import User
from test_hotel_january_journal_preparation import source

@compiles(BigInteger, "sqlite")
def sqlite_bigint(_type, _compiler, **_kw):
    return "INTEGER"

spec = importlib.util.spec_from_file_location("hotel_seed", Path(__file__).parents[1] / "scripts/seed_hotel_january_journals.py")
seed_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seed_module)


@pytest.fixture
def fixture_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    bu = BusinessUnit(id=2, code="HOTEL", name="Hotel", is_active=True)
    loc = Location(id=8, code="HOTEL", name="Hotel", business_unit_id=2, is_active=True)
    dep = Department(id=11, code="PMC", name="Pomec", business_unit_id=2, is_active=True)
    role = Role(name="SYSTEM_ADMINISTRATOR")
    actor = User(username="admin", full_name="Test admin", email="admin@test.invalid", password_hash="test", is_active=True, roles=[role])
    db.add_all([bu, loc, dep, actor]); db.flush()
    db.add(LocationDepartment(location_id=8, department_id=11))
    db.add(FiscalPeriod(fiscal_year=2026, fiscal_month=1, period_name="Jan2026", start_date=date(2026,1,1), end_date=date(2026,1,31), is_open=True, is_closed=False, allow_backdated_entries=True))
    db.add_all([
        ChartOfAccount(id=1, account_number="700-500-106", account_name="Repair", account_type="EXPENSE", normal_balance="DEBIT", is_active=True, is_posting=True),
        ChartOfAccount(id=2, account_number="100-100-100", account_name="Cash", account_type="ASSET", normal_balance="DEBIT", is_active=True, is_posting=True),
    ])
    db.commit()
    data = source()
    data["sheet"] = "test"
    mapping = {"source_sha256":"fixture", "scope":{"business_unit_id":2,"location_id":8},"departments":{"PMC":11}}
    yield db, actor, data, mapping
    db.close(); engine.dispose()


def test_dry_run_has_no_journal_ledger_or_audit_rows(fixture_db):
    db, actor, data, mapping = fixture_db
    result = seed_module.seed(db, data, mapping, actor, post=True)
    assert result["new_journals"] == 1
    assert db.query(JournalEntry).count() == db.query(GeneralLedger).count() == db.query(ImportRow).count() == 0


def test_post_seed_preserves_scope_audit_and_is_idempotent(fixture_db):
    db, actor, data, mapping = fixture_db
    result = seed_module.seed(db, copy.deepcopy(data), mapping, actor, apply=True, post=True)
    db.commit()
    journal = db.query(JournalEntry).one()
    assert journal.status == "POSTED"
    assert journal.business_unit_id == 2 and journal.location_id == 8
    assert journal.lines[0].department_id == 11
    assert db.query(GeneralLedger).count() == 2
    assert db.query(ImportRow).count() == 2
    assert result["created"][0]["register"] == "123"
    rerun = seed_module.seed(db, copy.deepcopy(data), mapping, actor, apply=True, post=True)
    assert rerun["new_journals"] == 0
    assert len(rerun["already_present"]) == 1
    assert db.query(JournalEntry).count() == 1 and db.query(GeneralLedger).count() == 2


def test_authorized_unbalanced_manual_source_posts_without_contra(fixture_db):
    db, actor, data, mapping = fixture_db
    data["journals"][0]["lines"] = [data["journals"][0]["lines"][1]]
    data["grand_total"]["debit"] = "0.00"
    result = seed_module.seed(db, data, mapping, actor, apply=True, post=True)
    journal = db.query(JournalEntry).one()
    assert journal.status == "POSTED" and len(journal.lines) == 1
    ledger = db.query(GeneralLedger).one()
    assert ledger.debit == 0 and ledger.credit == 100
    assert result["source_differences_preserved"][0]["difference"] == "-100.00"


def test_possible_previous_import_skipped_not_duplicated(fixture_db):
    db, actor, data, mapping = fixture_db
    db.add(JournalEntry(journal_number="OLD", posting_date=date(2026,1,31), reference_type="MANUAL", reference_id=0, document_number="same-reference", external_reference="JOURNAL_IMPORT:59:1", status="DRAFT", business_unit_id=2, location_id=8))
    db.commit()
    result = seed_module.seed(db, data, mapping, actor, apply=True, post=True)
    assert result["new_journals"] == 0 and len(result["skipped"]) == 1
    assert db.query(JournalEntry).count() == 1
    assert db.query(GeneralLedger).count() == 0


def test_transaction_rollback_removes_seed_and_gl(fixture_db):
    db, actor, data, mapping = fixture_db
    seed_module.seed(db, data, mapping, actor, apply=True, post=True)
    db.rollback()
    assert db.query(JournalEntry).count() == db.query(GeneralLedger).count() == db.query(ImportRow).count() == 0


def test_app_unpost_is_scoped_and_rerun_does_not_overwrite_correction(fixture_db):
    from app.services.accounting_unpost import unpost_journal
    db, actor, data, mapping = fixture_db
    other = copy.deepcopy(data["journals"][0])
    other.update(register="124", external_reference="HOTEL-JAN2026-REG-124")
    data["journals"].append(other)
    data["grand_total"] = {"debit":"200.00", "credit":"200.00"}
    seed_module.seed(db, copy.deepcopy(data), mapping, actor, apply=True, post=True)
    db.commit()
    journals = db.query(JournalEntry).order_by(JournalEntry.id).all()
    assert journals[0].document_number == journals[1].document_number
    unpost_journal(db, journal=journals[0], user=actor)
    assert journals[0].status == "DRAFT" and journals[1].status == "POSTED"
    assert db.query(GeneralLedger).count() == 2
    journals[0].lines[0].description = "Finance correction in app"
    db.commit()
    rerun = seed_module.seed(db, copy.deepcopy(data), mapping, actor, apply=True, post=True)
    assert rerun["new_journals"] == 0
    assert journals[0].status == "DRAFT"
    assert journals[0].lines[0].description == "Finance correction in app"
    assert db.query(GeneralLedger).count() == 2


def test_actor_requires_active_administrator(fixture_db):
    db, actor, _, _ = fixture_db
    assert seed_module.resolve_actor(db).id == actor.id
    actor.is_active = False
    db.flush()
    with pytest.raises(ValueError, match="SYSTEM_ADMINISTRATOR"):
        seed_module.resolve_actor(db, actor.id)
