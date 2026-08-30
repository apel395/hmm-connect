from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_item_master_replace_has_no_destructive_product_reset():
    source = (ROOT / "scripts" / "replace_item_master_20260830.py").read_text()

    assert "TRUNCATE TABLE products" not in source
    assert "--force-replace" not in source
    assert "repoint_generic_fks" in source
    assert "verify_reference_counts" in source


def test_empty_legacy_pr_is_not_eligible_for_po():
    source = (ROOT / "app" / "api" / "v1" / "purchase_requisitions.py").read_text()

    assert 'if payload["items"]:' in source
    assert '"MISSING_ITEMS"' in source


def test_new_pr_audit_contains_recovery_item_snapshot():
    source = (ROOT / "app" / "services" / "purchase_requisition_service.py").read_text()

    assert '"product_code": item.product.code' in source
    assert '"quantity": str(item.quantity)' in source
