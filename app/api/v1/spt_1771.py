from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_permission
from app.models.tax import CompanyTaxProfile, TaxCredit
from app.schemas.tax import (
    CompanyTaxProfileRead, CompanyTaxProfileUpsert,
    TaxCreditCreate, TaxCreditRead, TaxCreditUpdate,
)
from app.services.audit import record_audit
from app.services.spt_1771_service import SPT1771Service

router = APIRouter(prefix="/spt-1771", tags=["SPT Tahunan 1771"])


def _require(user, permission: str, detail: str):
    if not has_permission(user, permission):
        raise HTTPException(status_code=403, detail=detail)


def _profile_read(profile: CompanyTaxProfile) -> CompanyTaxProfileRead:
    return CompanyTaxProfileRead(
        id=profile.id, tax_year=profile.tax_year,
        npwp=profile.npwp, company_name=profile.company_name, address=profile.address,
        city=profile.city, klu=profile.klu, phone=profile.phone, email=profile.email,
        representative_name=profile.representative_name,
        created_at=profile.created_at, updated_at=profile.updated_at,
    )


@router.get("/report")
def spt_report(
    tax_year: int = Query(..., ge=2000, le=2100),
    location_id: int | None = None,
    department_id: int | None = None,
    business_unit_id: int | None = None,
    kompensasi_kerugian: Decimal | None = Query(default=None, ge=0),
    db: Session = Depends(get_db), user=Depends(get_current_user),
):
    _require(user, "fiscal.view", "Fiscal access required")
    try:
        return SPT1771Service(db).report(
            tax_year=tax_year, location_id=location_id,
            department_id=department_id, business_unit_id=business_unit_id,
            kompensasi_kerugian=kompensasi_kerugian,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/profile", response_model=CompanyTaxProfileRead | None)
def get_profile(
    tax_year: int = Query(..., ge=2000, le=2100),
    db: Session = Depends(get_db), user=Depends(get_current_user),
):
    _require(user, "fiscal.view", "Fiscal access required")
    profile = db.query(CompanyTaxProfile).filter(
        CompanyTaxProfile.tax_year == tax_year
    ).first()
    return _profile_read(profile) if profile else None


@router.put("/profile", response_model=CompanyTaxProfileRead)
def upsert_profile(
    tax_year: int = Query(..., ge=2000, le=2100),
    data: CompanyTaxProfileUpsert = ...,
    db: Session = Depends(get_db), user=Depends(get_current_user),
):
    _require(user, "fiscal.manage", "Fiscal manage access required")
    profile = db.query(CompanyTaxProfile).filter(
        CompanyTaxProfile.tax_year == tax_year
    ).first()
    if profile is None:
        profile = CompanyTaxProfile(tax_year=tax_year)
        db.add(profile)
    for field, value in data.model_dump().items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    record_audit(db, user, "TAX_PROFILE_UPSERTED", "COMPANY_TAX_PROFILE",
                 f"Upserted tax profile for tax year {tax_year}")
    return _profile_read(profile)


@router.get("/credits", response_model=list[TaxCreditRead])
def list_credits(
    tax_year: int = Query(..., ge=2000, le=2100),
    db: Session = Depends(get_db), user=Depends(get_current_user),
):
    _require(user, "fiscal.view", "Fiscal access required")
    rows = db.query(TaxCredit).filter(TaxCredit.tax_year == tax_year).all()
    return [TaxCreditRead.model_validate(row, from_attributes=True) for row in rows]


@router.post("/credits", response_model=TaxCreditRead, status_code=status.HTTP_201_CREATED)
def create_credit(
    data: TaxCreditCreate, db: Session = Depends(get_db), user=Depends(get_current_user),
):
    _require(user, "fiscal.manage", "Fiscal manage access required")
    credit = TaxCredit(**data.model_dump())
    db.add(credit)
    db.commit()
    db.refresh(credit)
    record_audit(db, user, "TAX_CREDIT_CREATED", "TAX_CREDIT",
                 f"Added {credit.credit_type} credit {credit.amount} for {credit.tax_year}")
    return TaxCreditRead.model_validate(credit, from_attributes=True)


@router.patch("/credits/{credit_id}", response_model=TaxCreditRead)
def update_credit(
    credit_id: int, data: TaxCreditUpdate,
    db: Session = Depends(get_db), user=Depends(get_current_user),
):
    _require(user, "fiscal.manage", "Fiscal manage access required")
    credit = db.get(TaxCredit, credit_id)
    if credit is None:
        raise HTTPException(status_code=404, detail="Tax credit not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(credit, field, value)
    db.commit()
    db.refresh(credit)
    record_audit(db, user, "TAX_CREDIT_UPDATED", "TAX_CREDIT", f"Updated tax credit {credit_id}")
    return TaxCreditRead.model_validate(credit, from_attributes=True)


@router.delete("/credits/{credit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_credit(
    credit_id: int, db: Session = Depends(get_db), user=Depends(get_current_user),
):
    _require(user, "fiscal.manage", "Fiscal manage access required")
    credit = db.get(TaxCredit, credit_id)
    if credit is None:
        raise HTTPException(status_code=404, detail="Tax credit not found")
    db.delete(credit)
    db.commit()
    record_audit(db, user, "TAX_CREDIT_DELETED", "TAX_CREDIT", f"Deleted tax credit {credit_id}")
