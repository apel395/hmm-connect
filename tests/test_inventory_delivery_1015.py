from datetime import timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException

from test_store_request_flow import store_db, make_request
from app.api.v1.store_requests import _row
from app.models.role import Role
from app.models.inventory import Inventory
from app.models.store_request import StoreIssue
from app.schemas.store_request import StoreRequestIssueCreate, StoreRequestIssueItem
from app.services.approval import _ensure_default_workflow
from app.services.store_request_service import StoreRequestService


def test_store_approval_defaults_and_preserves_custom_steps(store_db):
    db, *_ = store_db
    store = Role(name="STORE")
    db.add(store); db.flush()
    workflow = _ensure_default_workflow(db, workflow_code="SR_APPROVAL")
    assert [(step.name, step.approver_role_id) for step in workflow.steps] == [("Store Approval", store.id)]
    workflow.steps[0].name = "Existing store sign-off"
    assert _ensure_default_workflow(db, workflow_code="SR_APPROVAL").steps[0].name == "Existing store sign-off"


def test_issue_date_rejects_before_request_and_list_uses_posted_only(store_db):
    db, bu, department, location, warehouse, requester, store_user, products = store_db
    request = make_request(db, bu, department, location, warehouse, requester, products[:1], [3])
    db.add(Inventory(product_id=products[0].id, warehouse_id=warehouse.id, quantity=10, average_cost=10)); db.commit()
    payload = StoreRequestIssueCreate(issue_date=request.request_date-timedelta(days=1), items=[StoreRequestIssueItem(item_id=request.items[0].id, quantity=3)])
    with pytest.raises(HTTPException) as error:
        StoreRequestService.create_issue(db, request_id=request.id, data=payload, current_user=store_user)
    assert error.value.status_code == 400
    assert db.query(StoreIssue).count() == 0
    payload.issue_date = request.request_date
    issue = StoreRequestService.create_issue(db, request_id=request.id, data=payload, current_user=store_user)
    assert _row(request)["last_issue_date"] is None
    StoreRequestService.post_issue(db, issue_id=issue.id, current_user=store_user)
    db.refresh(request)
    assert _row(request)["last_issue_date"] == request.request_date
    assert db.query(Inventory).one().quantity == Decimal("7")
