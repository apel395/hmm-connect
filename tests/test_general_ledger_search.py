from app.api.v1.general_ledger import _search_pattern


def test_search_pattern_trims_document_number():
    assert _search_pattern("  PAY-202608-0023  ") == "%PAY-202608-0023%"


def test_search_pattern_ignores_blank_input():
    assert _search_pattern("   ") is None
    assert _search_pattern(None) is None
