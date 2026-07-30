from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.authorization import require_roles
from app.models.user import User
from app.schemas.purchasing_document import (
    PurchasingDocumentCreate,
    PurchasingDocumentListResponse,
    PurchasingDocumentRead,
    PurchasingDocumentSummary,
    PurchasingDocumentUpdate,
)
from app.services.purchasing_document_service import PurchasingDocumentService


router = APIRouter(
    prefix="/purchasing-documents",
    tags=["Purchasing Documents"],
)
authorized_user = require_roles("ADMIN", "PURCHASING", "FINANCE")


def filter_values(
    search: str | None = None,
    document_type: str | None = None,
    status: str | None = None,
    source_type: str | None = None,
    supplier_id: int | None = None,
    department_id: int | None = None,
    location_id: int | None = None,
    cashflow_stage: str | None = None,
    document_date_from: date | None = None,
    document_date_to: date | None = None,
    expected_payment_date_from: date | None = None,
    expected_payment_date_to: date | None = None,
    is_active: bool | None = None,
) -> dict:
    return {
        "search": search,
        "document_type": document_type,
        "status": status,
        "source_type": source_type,
        "supplier_id": supplier_id,
        "department_id": department_id,
        "location_id": location_id,
        "cashflow_stage": cashflow_stage,
        "document_date_from": document_date_from,
        "document_date_to": document_date_to,
        "expected_payment_date_from": expected_payment_date_from,
        "expected_payment_date_to": expected_payment_date_to,
        "is_active": is_active,
    }


@router.get("", response_model=PurchasingDocumentListResponse)
def list_purchasing_documents(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    filters: dict = Depends(filter_values),
    db: Session = Depends(get_db),
    _: User = Depends(authorized_user),
):
    if filters["is_active"] is None:
        filters["is_active"] = True
    return PurchasingDocumentService.list(db, page, page_size, filters)


@router.get("/summary", response_model=PurchasingDocumentSummary)
def purchasing_document_summary(
    filters: dict = Depends(filter_values),
    db: Session = Depends(get_db),
    _: User = Depends(authorized_user),
):
    return PurchasingDocumentService.summary(db, filters)


@router.post(
    "",
    response_model=PurchasingDocumentRead,
    status_code=201,
)
def create_purchasing_document(
    data: PurchasingDocumentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(authorized_user),
):
    document = PurchasingDocumentService.create(db, data, user)
    return PurchasingDocumentService.to_read(db, document)


@router.get("/{document_id}", response_model=PurchasingDocumentRead)
def get_purchasing_document(
    document_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(authorized_user),
):
    document = PurchasingDocumentService.get(db, document_id)
    return PurchasingDocumentService.to_read(db, document)


@router.patch("/{document_id}", response_model=PurchasingDocumentRead)
def update_purchasing_document(
    document_id: int,
    data: PurchasingDocumentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(authorized_user),
):
    document = PurchasingDocumentService.update(db, document_id, data, user)
    return PurchasingDocumentService.to_read(db, document)


@router.patch("/{document_id}/archive", response_model=PurchasingDocumentRead)
def archive_purchasing_document(
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(authorized_user),
):
    document = PurchasingDocumentService.set_active(db, document_id, False, user)
    return PurchasingDocumentService.to_read(db, document)


@router.patch("/{document_id}/restore", response_model=PurchasingDocumentRead)
def restore_purchasing_document(
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(authorized_user),
):
    document = PurchasingDocumentService.set_active(db, document_id, True, user)
    return PurchasingDocumentService.to_read(db, document)
