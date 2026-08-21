from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_any_role
from app.services.ar_reporting_service import ARReportingService

router = APIRouter(prefix="/ar-reporting", tags=["Accounts Receivable Reporting"])


def _require_access(user):
    if not has_any_role(user, "FINANCE", "AUDITOR", "GENERAL_MANAGER"):
        raise HTTPException(status_code=403, detail="Finance access required")


def _filters(customer_id: int | None, search: str | None):
    return {"customer_id": customer_id, "search": search}


@router.get("/summary")
def summary(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    customer_id: int | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _require_access(current_user)
    return ARReportingService(db).summary(
        page=page,
        page_size=page_size,
        **_filters(customer_id, search),
    )


@router.get("/detail")
def detail(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None, pattern="^(PAID|PARTIALLY_PAID|UNPAID)$"),
    customer_id: int | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _require_access(current_user)
    return ARReportingService(db).detail(
        page=page,
        page_size=page_size,
        status=status,
        **_filters(customer_id, search),
    )


@router.get("/aging")
def aging(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    customer_id: int | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _require_access(current_user)
    return ARReportingService(db).aging(
        page=page,
        page_size=page_size,
        **_filters(customer_id, search),
    )
