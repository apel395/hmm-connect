from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.dependencies.authorization import has_permission, require_permission
from app.services.location_access import assigned_location_id, require_location_access


def role(name: str, *codes: str):
    return SimpleNamespace(
        name=name,
        permissions=[SimpleNamespace(code=code) for code in codes],
    )


def user(*roles, location_id=None, default_location_id=None):
    return SimpleNamespace(
        roles=list(roles),
        location_id=location_id,
        default_location_id=default_location_id,
    )


def test_persisted_permission_mapping_is_authoritative():
    current = user(role("REQUESTER", "pr.view"))
    assert has_permission(current, "pr.view")
    assert not has_permission(current, "pr.create")
    with pytest.raises(HTTPException) as denied:
        require_permission("pr.create", "REQUESTER")(current_user=current)
    assert denied.value.status_code == 403


def test_unmapped_role_does_not_bypass_permission_requirement():
    current = user(role("REQUESTER"))
    with pytest.raises(HTTPException) as denied:
        require_permission("pr.create", "REQUESTER")(current_user=current)
    assert denied.value.status_code == 403


def test_manage_permission_grants_module_actions():
    current = user(role("FINANCE", "supplier_invoice.manage"))
    assert has_permission(current, "supplier_invoice.view")
    assert has_permission(current, "supplier_invoice.verify")
    assert not has_permission(current, "payment.manage")


def test_system_administrator_bypasses_permissions_and_location():
    current = user(role("SYSTEM_ADMINISTRATOR"), location_id=10)
    assert has_permission(current, "anything.manage")
    assert assigned_location_id(current) is None
    require_location_access(20, current)


def test_cross_location_access_is_hidden_with_404():
    current = user(role("DEPARTMENT", "pr.view"), location_id=10)
    with pytest.raises(HTTPException) as hidden:
        require_location_access(20, current)
    assert hidden.value.status_code == 404


def test_user_without_assigned_location_keeps_compatibility():
    current = user(role("DEPARTMENT", "pr.view"))
    assert assigned_location_id(current) is None
    require_location_access(20, current)


def test_purchase_order_and_receiving_details_hide_cross_location_documents():
    from app.api.v1.goods_receipts import get_receipt
    from app.api.v1.purchase_orders import get_purchase_order

    class FakeDb:
        def get(self, _model, _document_id):
            return SimpleNamespace(location_id=20)

    current = user(role("PURCHASING", "po.manage", "receiving.manage"), location_id=10)
    with pytest.raises(HTTPException) as purchase_order_hidden:
        get_purchase_order(1, FakeDb(), current)
    assert purchase_order_hidden.value.status_code == 404

    with pytest.raises(HTTPException) as receipt_hidden:
        get_receipt(1, FakeDb(), current)
    assert receipt_hidden.value.status_code == 404


def test_operational_lists_apply_location_scope():
    import inspect

    from app.api.v1.goods_receipts import (
        list_receipts,
        list_receivable_purchase_orders,
    )
    from app.api.v1.purchase_orders import list_purchase_orders

    assert "apply_location_scope" in inspect.getsource(list_purchase_orders)
    assert "apply_location_scope" in inspect.getsource(list_receipts)
    assert "apply_location_scope" in inspect.getsource(list_receivable_purchase_orders)


def test_supplier_invoice_validation_enforces_inherited_source_location():
    import inspect

    from app.services.supplier_invoice_service import SupplierInvoiceService

    source = inspect.getsource(SupplierInvoiceService.validate)
    assert "enforce_location_access(user, data.location_id)" in source
