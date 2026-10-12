from datetime import datetime, timezone
from types import SimpleNamespace as NS
import pytest
from fastapi import HTTPException
from app.services import receiving_edit_policy as policy
from app.api.v1 import goods_receipts as api


def user(*permissions): return NS(permissions=set(permissions))
def receipt(status="DRAFT"): return NS(id=707, status=status, receipt_number="GR-TEST", source_type="LIVE")
def approval():
    return NS(status="APPROVED", completed_at=datetime(2026,10,9,tzinfo=timezone.utc), current_step_order=None,
        steps=[NS(id=i, step_order=i, name=f"Stage {i}", status="APPROVED", approved_by_id=45,
            decided_at=datetime(2026,10,9,tzinfo=timezone.utc), decision_comment="OK") for i in (1,2,3)])

@pytest.fixture(autouse=True)
def mock_permission_checks(monkeypatch):
    monkeypatch.setattr(policy, "has_permission", lambda u,p: p in u.permissions)

@pytest.mark.parametrize("permissions,allowed", [([],False),(["receiving.edit"],False),(["receiving.manage"],False),(["receiving.edit","receiving.manage"],True)])
def test_approved_draft_edit_requires_both_permissions(permissions, allowed):
    assert policy.can_edit_receiving(receipt(), approval(), user(*permissions)) is allowed


def test_posted_receipt_cannot_be_fully_edited_even_by_manager():
    assert not policy.can_edit_receiving(receipt("POSTED"), approval(), user("receiving.edit","receiving.manage"))


def test_reopening_preserves_old_decisions_in_audit_and_invalidates_post(monkeypatch):
    doc, request = receipt(), approval()
    manager = user("receiving.edit","receiving.manage")
    audit=[]
    monkeypatch.setattr(policy,"get_request",lambda *a,**kw: request)
    monkeypatch.setattr(policy.ActivityService,"log",lambda **kw:audit.append(kw))
    assert policy.reopen_approved_receiving(None,doc,manager)
    assert request.status == "PENDING" and request.current_step_order == 1 and request.completed_at is None
    assert [s.status for s in request.steps] == ["PENDING","WAITING","WAITING"]
    assert all(s.approved_by_id is None and s.decided_at is None for s in request.steps)
    assert audit[0]["before_data"]["steps"][0]["approved_by_id"] == 45
    assert audit[0]["before_data"]["steps"][0]["decision_comment"] == "OK"
    monkeypatch.setattr(api,"_scoped_receipt_for_update",lambda *a:doc)
    monkeypatch.setattr(api,"get_request",lambda *a:request)
    with pytest.raises(HTTPException) as error: api.post_receipt(707,None,manager)
    assert error.value.status_code == 409


def test_denied_edit_does_not_reset_decisions(monkeypatch):
    request=approval()
    monkeypatch.setattr(policy,"get_request",lambda *a,**kw:request)
    with pytest.raises(HTTPException): policy.reopen_approved_receiving(None,receipt(),user("receiving.edit"))
    assert request.status == "APPROVED" and request.steps[0].approved_by_id == 45


def test_unsubmitted_and_pending_policy_is_preserved(monkeypatch):
    editor=user("receiving.edit")
    assert policy.can_edit_receiving(receipt(),None,editor)
    request=NS(status="PENDING")
    monkeypatch.setattr(policy,"can_user_edit_pending_approval",lambda *a:True)
    assert policy.can_edit_receiving(receipt(),request,editor)
    monkeypatch.setattr(policy,"can_user_edit_pending_approval",lambda *a:False)
    assert not policy.can_edit_receiving(receipt(),request,editor)


def test_direct_use_post_does_not_write_inventory_or_movements(monkeypatch):
    from decimal import Decimal
    from app.models.goods_receipt import GoodsReceipt
    from app.models.inventory import Inventory
    from app.models.stock_movement import StockMovement
    from app.services.goods_receipt_service import GoodsReceiptService
    line=NS(id=1,product_id=10,product=NS(inventory_treatment="STOCK",code="WATER"),quantity=Decimal("10"),unit_cost=Decimal("5000"),is_taxable=False,tax_rate=Decimal("0"))
    doc=NS(id=707,receipt_number="GR-TEST",status="DRAFT",source_type="LIVE",received_at=datetime(2026,10,9,tzinfo=timezone.utc),purchase_order_id=None,destination_type="DIRECT_USE",warehouse_id=None,items=[line])
    class Query:
        def filter(self,*a): return self
        def with_for_update(self): return self
        def first(self): return doc
    class Db:
        def query(self,model):
            assert model is GoodsReceipt, "Direct-use posting accessed a stock table"
            return Query()
        def add(self,value): assert not isinstance(value,(Inventory,StockMovement))
        def flush(self): pass
        def commit(self): pass
        def refresh(self,value): pass
    monkeypatch.setattr(GoodsReceiptService,"_check_access",lambda *a:None)
    monkeypatch.setattr(GoodsReceiptService,"_sync_accounting_journal",lambda *a,**kw:None)
    monkeypatch.setattr(policy.ActivityService,"log",lambda **kw:None)
    monkeypatch.setattr("app.services.goods_receipt_service.FiscalPeriodService.validate_posting_date",lambda *a,**kw:None)
    result=GoodsReceiptService.post(Db(),receipt_id=707,user=user())
    assert result.status == "POSTED" and result.total_amount == Decimal("50000")
