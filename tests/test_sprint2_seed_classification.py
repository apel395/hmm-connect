from collections import Counter
from types import SimpleNamespace

from app.seeds.chart_of_accounts import (
    DEFAULT_CHART_OF_ACCOUNTS,
    INPUT_VAT_ACCOUNT_NUMBER,
    PETTY_CASH_BUSINESS_UNITS,
    _account_type,
)
from scripts.reclassify_dairy_groceries import is_canned, is_dairy


def product(name: str, uom: str = "KG", usage_uom: str = "KG"):
    return SimpleNamespace(name=name, uom=uom, usage_uom=usage_uom)


def test_pak_ardi_source_codes_are_unique_and_input_vat_is_valid():
    counts = Counter(row[0] for row in DEFAULT_CHART_OF_ACCOUNTS)
    assert len(DEFAULT_CHART_OF_ACCOUNTS) == 302
    assert not [code for code, count in counts.items() if count > 1]
    vat = next(row for row in DEFAULT_CHART_OF_ACCOUNTS if row[0] == INPUT_VAT_ACCOUNT_NUMBER)
    assert vat[1:5] == ("Pajak Ppn Masukan", "ASSET", "DEBIT", "ACCOUNT")
    assert _account_type("", "OPERATING EXPENSES") == "EXPENSE"


def test_expected_petty_cash_leaf_payload_is_complete():
    expected = {f"100-100-{suffix}" for suffix in [
        "100", "101", "102", "103", "104", "105", "106", "107",
        "108", "109", "110", "111", "112", "990",
    ]}
    assert set(PETTY_CASH_BUSINESS_UNITS) == expected
    rows = {row[0]: row for row in DEFAULT_CHART_OF_ACCOUNTS}
    assert all(rows[code][4] == "ACCOUNT" and rows[code][5] == "PETTY_CASH" for code in expected)


def test_dairy_matching_and_obvious_false_positives():
    for name in ["Fresh Milk", "Susu UHT", "Greek Yogurt", "Whipping Cream", "Cheddar Cheese", "Salted Butter"]:
        assert is_dairy(product(name)), name
    for name in ["Milk Tea Powder", "Cream Cleaner", "Butter Knife", "Cheese Cloth", "Body Milk", "Margarine"]:
        assert not is_dairy(product(name)), name


def test_canned_matching_is_explicit_and_has_priority_signal():
    assert is_canned(product("Canned Evaporated Milk"))
    assert is_dairy(product("Canned Evaporated Milk"))
    assert is_canned(product("Tuna", uom="CAN"))
    assert is_canned(product("Buah Kaleng"))
    assert not is_canned(product("Candy"))
