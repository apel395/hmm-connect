from decimal import Decimal
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import require_roles
from app.models.inventory import Inventory
from app.models.store_request import StoreIssue, StoreRequest
from app.models.user import User
from app.schemas.approval import ApprovalDecisionRequest
from app.schemas.store_request import StoreRequestCreate, StoreRequestIssueCreate
from app.services.document_context import document_context, print_metadata
from app.services.store_request_service import StoreRequestService
from app.services.location_access import apply_location_scope, enforce_location_access


router = APIRouter(prefix="/store-requests", tags=["Store Requests"])
requester_user = require_roles("REQUESTER")
warehouse_user = require_roles("WAREHOUSE")


def _row(request: StoreRequest, requester_name: str | None = None) -> dict:
    total_requested = sum((Decimal(item.requested_quantity or 0) for item in request.items), Decimal("0"))
    total_issued = sum((Decimal(item.issued_quantity or 0) for item in request.items), Decimal("0"))
    return {
        "id": request.id,
        "sr_number": request.sr_number,
        "status": request.status,
        "request_date": request.request_date,
        "requester_name": requester_name or (request.requested_by.full_name if request.requested_by else None),
        "business_unit_id": request.business_unit_id,
        "business_unit_name": request.business_unit.name if request.business_unit else None,
        "department_id": request.department_id,
        "department_name": request.department.name if request.department else None,
        "location_id": request.location_id,
        "location_name": request.location.name if request.location else None,
        "warehouse_id": request.warehouse_id,
        "warehouse_code": request.warehouse.code if request.warehouse else None,
        "warehouse_name": request.warehouse.name if request.warehouse else None,
        "total_requested_quantity": total_requested,
        "total_issued_quantity": total_issued,
        "total_remaining_quantity": total_requested - total_issued,
    }


def _issue_payload(issue: StoreIssue) -> dict:
    return {
        "id": issue.id,
        "issue_number": issue.issue_number,
        "status": issue.status,
        "notes": issue.notes,
        "created_at": issue.created_at,
        "posted_at": issue.posted_at,
        "items": [
            {
                "id": item.id,
                "store_request_item_id": item.store_request_item_id,
                "product_id": item.product_id,
                "product_code": item.product.code,
                "product_name": item.product.name,
                "quantity": item.quantity,
                "uom": item.store_request_item.uom,
            }
            for item in issue.items
        ],
    }


def _detail(db: Session, request: StoreRequest, user) -> dict:
    inventory_rows = {
        row.product_id: row
        for row in db.query(Inventory).filter(Inventory.warehouse_id == request.warehouse_id).all()
    }
    payload = {
        **_row(request),
        "notes": request.notes,
        "created_at": request.created_at,
        "updated_at": request.updated_at,
        "items": [],
        "issues": [_issue_payload(issue) for issue in sorted(request.issues, key=lambda row: row.id, reverse=True)],
    }
    for item in request.items:
        inventory = inventory_rows.get(item.product_id)
        requested = Decimal(item.requested_quantity or 0)
        issued = Decimal(item.issued_quantity or 0)
        available = Decimal(inventory.quantity or 0) if inventory else Decimal("0")
        payload["items"].append({
            "id": item.id,
            "product_id": item.product_id,
            "product_code": item.product.code,
            "product_name": item.product.name,
            "uom": item.uom,
            "requested_quantity": requested,
            "issued_quantity": issued,
            "remaining_quantity": requested - issued,
            "available_stock": available,
        })
    payload.update(document_context(db, "STORE_REQUEST", request.id, request.status, user))
    return payload


@router.get("")
def list_store_requests(
    status: str | None = Query(default=None, max_length=30),
    search: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    query = db.query(StoreRequest, User.full_name).outerjoin(User, User.id == StoreRequest.requested_by_id)
    query = apply_location_scope(query, StoreRequest, user)
    if status and status.upper() != "ALL":
        query = query.filter(StoreRequest.status == status.upper())
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(or_(StoreRequest.sr_number.ilike(term), User.full_name.ilike(term)))
    total = query.count()
    rows = query.order_by(StoreRequest.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    total_pages = ceil(total / page_size) if total else 0
    counts_query = apply_location_scope(db.query(StoreRequest.status, func.count(StoreRequest.id)), StoreRequest, user)
    status_counts = dict(counts_query.group_by(StoreRequest.status).all())
    return {
        "items": [_row(request, requester_name) for request, requester_name in rows],
        "page": page,
        "page_size": page_size,
        "total_items": total,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_previous": page > 1,
        "summary": {"status_counts": status_counts},
    }


@router.get("/availability")
def warehouse_availability(
    warehouse_id: int,
    product_ids: list[int] = Query(default=[]),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    if not product_ids:
        return []
    rows = db.query(Inventory).filter(
        Inventory.warehouse_id == warehouse_id,
        Inventory.product_id.in_(set(product_ids)),
    ).all()
    quantities = {row.product_id: Decimal(row.quantity or 0) for row in rows}
    return [
        {"product_id": product_id, "available_stock": quantities.get(product_id, Decimal("0"))}
        for product_id in dict.fromkeys(product_ids)
    ]


@router.get("/{request_id}")
def get_store_request(request_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    request = db.get(StoreRequest, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Store Request not found")
    enforce_location_access(user, request.location_id)
    return _detail(db, request, user)


@router.get("/{request_id}/print")
def print_store_request(request_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return {**get_store_request(request_id, db, user), "document_type": "Store Request", **print_metadata(user)}


@router.post("", status_code=201)
def create_store_request(data: StoreRequestCreate, db: Session = Depends(get_db), user=Depends(requester_user)):
    return _detail(db, StoreRequestService.create(db=db, data=data, current_user=user), user)


@router.patch("/{request_id}")
@router.put("/{request_id}")
def update_store_request(request_id: int, data: StoreRequestCreate, db: Session = Depends(get_db), user=Depends(requester_user)):
    return _detail(db, StoreRequestService.update(db=db, request_id=request_id, data=data, current_user=user), user)


@router.post("/{request_id}/submit")
def submit_store_request(request_id: int, db: Session = Depends(get_db), user=Depends(requester_user)):
    return _detail(db, StoreRequestService.submit(db=db, request_id=request_id, current_user=user), user)


@router.post("/{request_id}/approve")
def approve_store_request(request_id: int, data: ApprovalDecisionRequest | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return _detail(db, StoreRequestService.approve(db=db, request_id=request_id, data=data, current_user=user), user)


@router.post("/{request_id}/reject")
def reject_store_request(request_id: int, data: ApprovalDecisionRequest | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return _detail(db, StoreRequestService.reject(db=db, request_id=request_id, data=data, current_user=user), user)


@router.post("/{request_id}/issues", status_code=201)
def create_store_issue(request_id: int, data: StoreRequestIssueCreate, db: Session = Depends(get_db), user=Depends(warehouse_user)):
    return _issue_payload(StoreRequestService.create_issue(db=db, request_id=request_id, data=data, current_user=user))


@router.post("/issues/{issue_id}/post")
def post_store_issue(issue_id: int, db: Session = Depends(get_db), user=Depends(warehouse_user)):
    return _issue_payload(StoreRequestService.post_issue(db=db, issue_id=issue_id, current_user=user))
