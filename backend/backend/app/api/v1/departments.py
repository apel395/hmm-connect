from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.department import Department
from app.schemas.department import DepartmentCreate, DepartmentResponse, DepartmentUpdate
from app.services.audit import record_audit

router = APIRouter(prefix="/departments", tags=["Departments"])


@router.get("", response_model=list[DepartmentResponse])
def get_departments(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return db.query(Department).filter(Department.is_active.is_(True)).order_by(Department.name).all()


@router.post("", response_model=DepartmentResponse, status_code=201)
def create_department(
    data: DepartmentCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    code = data.code.strip().upper()
    name = data.name.strip()

    if db.query(Department).filter(Department.code == code).first():
        raise HTTPException(status_code=409, detail="Department code already exists")
    if db.query(Department).filter(Department.name == name).first():
        raise HTTPException(status_code=409, detail="Department name already exists")

    department = Department(code=code, name=name)
    db.add(department)
    db.flush()

    record_audit(
        db=db,
        user=current_user,
        action="CREATE",
        entity_type="DEPARTMENT",
        entity_id=department.id,
        summary=f"Created department {department.name}",
        details={"code": department.code},
    )

    db.commit()
    db.refresh(department)
    return department


@router.patch("/{department_id}", response_model=DepartmentResponse)
def update_department(
    department_id: int,
    data: DepartmentUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")

    before = {"name": department.name, "is_active": department.is_active}
    if data.name is not None:
        department.name = data.name.strip()
    if data.is_active is not None:
        department.is_active = data.is_active

    record_audit(
        db=db,
        user=current_user,
        action="UPDATE",
        entity_type="DEPARTMENT",
        entity_id=department.id,
        summary=f"Updated department {department.name}",
        details={"before": before, "after": {"name": department.name, "is_active": department.is_active}},
    )

    db.commit()
    db.refresh(department)
    return department
