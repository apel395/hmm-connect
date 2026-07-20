from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.security import hash_password
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.role import Role
from app.models.department import Department
from app.models.location import Location
from app.services.audit import record_audit
from app.schemas.user import (
    AssignDepartmentRequest,
    AssignLocationRequest,
    AssignRoleRequest,
    CreateUserRequest,
    UserResponse,
)

router = APIRouter(prefix="/users", tags=["Users"])


def user_query(db: Session):
    return db.query(User).options(
        joinedload(User.department),
        joinedload(User.location),
        joinedload(User.roles),
    )


@router.get("", response_model=list[UserResponse])
def get_users(
    db: Session = Depends(get_db),
    current=Depends(get_current_user),
):
    return user_query(db).order_by(User.full_name).all()


@router.post("", response_model=UserResponse, status_code=201)
def create_user(
    data: CreateUserRequest,
    db: Session = Depends(get_db),
    current=Depends(get_current_user),
):
    if db.query(User).filter(User.username == data.username.strip()).first():
        raise HTTPException(status_code=409, detail="Username already exists")
    if db.query(User).filter(User.email == str(data.email).lower()).first():
        raise HTTPException(status_code=409, detail="Email already exists")

    department = None
    if data.department_id is not None:
        department = db.query(Department).filter(Department.id == data.department_id).first()
        if not department:
            raise HTTPException(status_code=404, detail="Department not found")

    location = None
    if data.location_id is not None:
        location = db.query(Location).filter(Location.id == data.location_id).first()
        if not location:
            raise HTTPException(status_code=404, detail="Location not found")

    role = None
    if data.role_id is not None:
        role = db.query(Role).filter(Role.id == data.role_id).first()
        if not role:
            raise HTTPException(status_code=404, detail="Role not found")

    user = User(
        username=data.username.strip(),
        email=str(data.email).lower(),
        full_name=data.full_name.strip(),
        password_hash=hash_password(data.password),
        is_active=True,
        department=department,
        location=location,
    )
    if role:
        user.roles.append(role)

    db.add(user)
    db.flush()

    record_audit(
        db=db,
        user=current,
        action="CREATE",
        entity_type="USER",
        entity_id=user.id,
        summary=f"Created user {user.username}",
        details={
            "username": user.username,
            "department_id": user.department_id,
            "location_id": user.location_id,
            "role_id": role.id if role else None,
        },
    )

    db.commit()
    return user_query(db).filter(User.id == user.id).first()


@router.post("/{user_id}/roles", response_model=UserResponse)
def assign_role(
    user_id: int,
    data: AssignRoleRequest,
    db: Session = Depends(get_db),
    current=Depends(get_current_user),
):
    user = user_query(db).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    role = db.query(Role).filter(Role.id == data.role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    if role not in user.roles:
        user.roles.append(role)

    record_audit(
        db=db,
        user=current,
        action="ASSIGN_ROLE",
        entity_type="USER",
        entity_id=user.id,
        summary=f"Assigned role {role.name} to {user.username}",
        details={"role_id": role.id, "role_name": role.name},
    )

    db.commit()
    return user_query(db).filter(User.id == user.id).first()


@router.delete("/{user_id}/roles/{role_id}", response_model=UserResponse)
def remove_role(
    user_id: int,
    role_id: int,
    db: Session = Depends(get_db),
    current=Depends(get_current_user),
):
    user = user_query(db).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    if role in user.roles:
        user.roles.remove(role)

    record_audit(
        db=db,
        user=current,
        action="REMOVE_ROLE",
        entity_type="USER",
        entity_id=user.id,
        summary=f"Removed role {role.name} from {user.username}",
        details={"role_id": role.id, "role_name": role.name},
    )

    db.commit()
    return user_query(db).filter(User.id == user.id).first()


@router.patch("/{user_id}/department", response_model=UserResponse)
def assign_department(
    user_id: int,
    data: AssignDepartmentRequest,
    db: Session = Depends(get_db),
    current=Depends(get_current_user),
):
    user = user_query(db).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    department = None
    if data.department_id is not None:
        department = db.query(Department).filter(Department.id == data.department_id).first()
        if not department:
            raise HTTPException(status_code=404, detail="Department not found")

    user.department_id = data.department_id

    record_audit(
        db=db,
        user=current,
        action="ASSIGN_DEPARTMENT",
        entity_type="USER",
        entity_id=user.id,
        summary=f"Assigned department to {user.username}",
        details={
            "department_id": department.id if department else None,
            "department_name": department.name if department else None,
        },
    )

    db.commit()
    return user_query(db).filter(User.id == user.id).first()


@router.patch("/{user_id}/location", response_model=UserResponse)
def assign_location(
    user_id: int,
    data: AssignLocationRequest,
    db: Session = Depends(get_db),
    current=Depends(get_current_user),
):
    user = user_query(db).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    location = None
    if data.location_id is not None:
        location = db.query(Location).filter(Location.id == data.location_id).first()
        if not location:
            raise HTTPException(status_code=404, detail="Location not found")

    user.location_id = data.location_id

    record_audit(
        db=db,
        user=current,
        action="ASSIGN_LOCATION",
        entity_type="USER",
        entity_id=user.id,
        summary=f"Assigned location to {user.username}",
        details={
            "location_id": location.id if location else None,
            "location_name": location.name if location else None,
        },
    )

    db.commit()
    return user_query(db).filter(User.id == user.id).first()
