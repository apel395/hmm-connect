import copy
from datetime import date
import importlib.util
import json
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


def test_explicit_account_department_handles_unprefixed_room_revenue():
    data = source()
    data["journals"][0]["lines"][0].update(department_prefix=None, suggested_department=None)
    mapping = review()
    mapping["departments"] = {}
    mapping["account_departments"] = {"547001": 11}
    plan = prep.build_plan(data, database(), mapping)
    assert plan["summary"]["statuses"] == {"READY_FOR_SEED_REVIEW": 1}
    assert plan["source"]["journals"][0]["lines"][0]["department_id"] == 11


@pytest.mark.parametrize("existing_unit,expected_overlap", [(2, True), (3, False)])
def test_legacy_import_reference_overlap_is_scoped_and_detected_across_dates(existing_unit, expected_overlap):
    db = database()
    db["journals"] = [{"id": 8, "external_reference": "JOURNAL_IMPORT:59:1", "journal_number": "MAN-8", "document_number": " SAME-REFERENCE ", "status": "DRAFT", "posting_date": "2026-01-31", "business_unit_id": existing_unit, "location_id": 8}]
    plan = prep.build_plan(source(), db, review())
    journal = plan["source"]["journals"][0]
    assert ("SOURCE_REFERENCE_OVERLAP_REVIEW" in journal["issues"]) is expected_overlap
    if expected_overlap:
        assert journal["possible_existing_journals"][0]["id"] == 8
    assert journal["posting_date"] == "2026-01-15"  # No source date correction.


def test_prepared_manifest_keeps_unresolved_controls_out_of_applied_mapping():
    path = Path(__file__).parents[1] / "scripts/hotel_january_2026_mapping.json"
    mapping = json.loads(path.read_text())
    assert mapping["accounts"]["201101"] == "200-100-1"
    assert not (set(mapping["accounts"]) & set(mapping["review_required_accounts"]))
    assert "103085" in mapping["review_required_accounts"]  # OTA advance is not automatically a liability.
    assert "202014" in mapping["review_required_accounts"]  # Payable not reclassified to expense.
    assert "SWP" not in mapping["departments"]
    assert "BOD" not in mapping["departments"]
    assert mapping["departments"]["LDY"] == 14


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
