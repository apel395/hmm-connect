import copy
from datetime import date
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("hotel_jan_prep", Path(__file__).parents[1] / "scripts/prepare_hotel_january_journals.py")
prep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prep)


def source():
    return {"source_sha256": "fixture", "source_file": "fixture.xls", "missing_sequences": [],
            "grand_total": {"debit": "100.00", "credit": "100.00"},
            "journals": [{"register": "123", "external_reference": "HOTEL-JAN2026-REG-123", "header_row": 12,
                "posting_date": "2026-01-15", "description": "test", "invoice_reference": "same-reference",
                "lines": [
                    {"source_row": 14, "sequence": 1, "posting_date": "2026-01-15", "legacy_code": "547001", "legacy_name": "PMC - Expense", "source_account_code": "700-500-106", "account_code": "700-500-106", "department_prefix": "PMC", "suggested_department": "Pomec", "debit": "100.00", "credit": "0.00", "source_dc": "C"},
                    {"source_row": 15, "sequence": 2, "posting_date": "2026-01-15", "legacy_code": "101101", "legacy_name": "Cash", "source_account_code": "100-100-100", "account_code": "100-100-100", "department_prefix": None, "suggested_department": None, "debit": "0.00", "credit": "100.00", "source_dc": "C"}]}]}


def database():
    return {"accounts": [{"id": 1, "account_number": "700-500-106", "account_type": "EXPENSE", "is_active": True, "is_posting": True},
                         {"id": 2, "account_number": "100-100-100", "account_type": "ASSET", "is_active": True, "is_posting": True}],
            "units": [{"id": 2, "name": "Hotel", "is_active": True}],
            "locations": [{"id": 8, "business_unit_id": 2, "is_active": True}],
            "departments": [{"id": 11, "business_unit_id": 2, "is_active": True}],
            "location_departments": [{"location_id": 8, "department_id": 11}],
            "periods": [{"is_open": True, "is_closed": False, "allow_backdated_entries": True, "start_date": date(2026, 1, 1), "end_date": date(2026, 1, 31)}],
            "journals": []}


def review():
    return {"source_sha256": "fixture", "scope": {"business_unit_id": 2, "location_id": 8}, "departments": {"PMC": 11}}


def test_amount_columns_override_conflicting_dc_labels_without_flipping():
    plan = prep.build_plan(source(), database(), review())
    assert plan["summary"]["dc_label_conflicts_using_amount_columns"] == 1
    assert plan["summary"]["statuses"] == {"READY_FOR_SEED_REVIEW": 1}
    assert plan["source"]["journals"][0]["lines"][0]["debit"] == "100.00"
    assert plan["summary"]["seed_ready"] is False  # Preparation never authorizes writes.


def test_unbalanced_register_kept_without_fabricated_contra():
    data = source()
    data["journals"][0]["lines"][0]["debit"] = "55.00"
    data["grand_total"]["debit"] = "55.00"
    plan = prep.build_plan(data, database(), review())
    assert plan["summary"]["unbalanced_registers"][0]["difference"] == "-45.00"
    assert len(plan["source"]["journals"][0]["lines"]) == 2


def test_missing_coa_and_department_stay_unresolved():
    data = source()
    data["journals"][0]["lines"][0]["source_account_code"] = None
    plan = prep.build_plan(data, database())
    assert plan["summary"]["unmapped_nonzero_lines"] == 1
    assert "DEPARTMENT_CONFIRMATION_REQUIRED" in plan["source"]["journals"][0]["issues"]
    assert "HOTEL_SCOPE_CONFIRMATION_REQUIRED" in plan["source"]["journals"][0]["issues"]


@pytest.mark.parametrize("field,value", [("is_posting", False), ("is_active", False), ("account_type", "STATISTIC")])
def test_nonfinancial_or_inactive_targets_blocked(field, value):
    db = database()
    db["accounts"][0][field] = value
    plan = prep.build_plan(source(), db, review())
    assert "COA_NOT_ACTIVE_FINANCIAL_POSTING_ACCOUNT" in plan["source"]["journals"][0]["issues"]


def test_closed_period_and_unlinked_department_blocked():
    db = database()
    db["periods"][0]["is_closed"] = True
    db["location_departments"] = []
    plan = prep.build_plan(source(), db, review())
    assert "JANUARY_PERIOD_NOT_OPEN_FOR_HISTORICAL_ENTRY" in plan["source"]["journals"][0]["issues"]
    assert "DEPARTMENT_NOT_IN_HOTEL_LOCATION" in plan["source"]["journals"][0]["issues"]


def test_existing_void_register_not_silently_reimported():
    db = database()
    db["journals"] = [{"id": 1, "external_reference": "HOTEL-JAN2026-REG-123", "journal_number": "MAN-1", "document_number": None, "status": "VOID"}]
    plan = prep.build_plan(source(), db, review())
    assert "EXISTING_REGISTER_REVIEW" in plan["source"]["journals"][0]["issues"]


def test_same_invoice_reference_does_not_merge_distinct_registers():
    data = source()
    other = copy.deepcopy(data["journals"][0])
    other.update(register="124", external_reference="HOTEL-JAN2026-REG-124")
    data["journals"].append(other)
    data["grand_total"] = {"debit": "200.00", "credit": "200.00"}
    assert prep.build_plan(data)["summary"]["journals"] == 2


def test_source_total_mismatch_and_mapping_hash_rejected():
    data = source()
    data["grand_total"]["debit"] = "99.00"
    with pytest.raises(ValueError, match="grand totals"):
        prep.build_plan(data)
    with pytest.raises(ValueError, match="hash mismatch"):
        prep.build_plan(source(), review={"source_sha256": "wrong"})


def test_pre_2026_date_blocked_instead_of_converted():
    data = source()
    data["journals"][0]["posting_date"] = "2025-12-31"
    assert "OUTSIDE_JANUARY_2026" in prep.build_plan(data)["source"]["journals"][0]["issues"]


def test_mapping_review_not_overwritten(tmp_path):
    plan = prep.build_plan(source())
    output = tmp_path / "plan"
    mapping = tmp_path / "plan-mapping-template.json"
    mapping.write_text("finance's existing review")
    prep.write_outputs(plan, output)
    assert mapping.read_text() == "finance's existing review"


def test_unexpected_source_hash_rejected_before_reading_workbook(tmp_path):
    path = tmp_path / "other.xls"
    path.write_bytes(b"changed source")
    with pytest.raises(ValueError, match="Source hash changed"):
        prep.read_source(path)
