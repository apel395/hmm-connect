from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.security import hash_password
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import is_superuser
from app.models.department import Department
from app.models.location import Location
from app.models.role import Role
from app.models.user import User
from app.schemas.auth import RoleSummary
from app.schemas.user import (
    DepartmentSummary,
    LocationSummary,
    UserCreate,
    UserDetailResponse,
    UserResponse,
    UserRolesUpdate,
    UserUpdate,
)
from app.services.audit import record_audit

router = APIRouter(prefix="/users", tags=["Users"])


def has_admin_role(user: User) -> bool:
    return is_superuser(user)


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not is_superuser(user):
        raise HTTPException(status_code=403, detail="Administrator access required")
    return user


def editable_user_query(db: Session):
    return db.query(User).options(
        selectinload(User.department),
        selectinload(User.location),
        selectinload(User.roles).selectinload(Role.permissions),
    )


def user_detail(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "is_active": user.is_active,
        "department_id": user.department_id,
        "location_id": user.location_id,
        "default_business_unit_id": user.default_business_unit_id,
        "default_location_id": user.default_location_id,
        "default_department_id": user.default_department_id,
        "department": user.department,
        "location": user.location,
        "role_ids": [role.id for role in user.roles],
        "roles": user.roles,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


def get_editable_user(db: Session, user_id: int) -> User:
    user = editable_user_query(db).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _validate_roles(db: Session, role_ids: list[int]) -> list[Role]:
    roles = db.query(Role).options(selectinload(Role.permissions)).filter(Role.id.in_(role_ids)).all() if role_ids else []
    missing = sorted(set(role_ids) - {role.id for role in roles})
    if missing:
        raise HTTPException(status_code=422, detail={"message": "One or more roles do not exist", "role_ids": missing})
    return roles


@router.get("", response_model=list[UserResponse])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return editable_user_query(db).order_by(User.username).all()


@router.post("", response_model=UserDetailResponse, status_code=201)
def create_user(data: UserCreate, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    if db.query(User.id).filter(User.username == data.username).first():
        raise HTTPException(409, "Username is already in use")
    if db.query(User.id).filter(User.email == data.email).first():
        raise HTTPException(409, "Email is already in use")
    if data.department_id is not None and not db.get(Department, data.department_id):
        raise HTTPException(422, "Department does not exist")
    if data.location_id is not None and not db.get(Location, data.location_id):
        raise HTTPException(422, "Location does not exist")
    roles = _validate_roles(db, data.role_ids)
    user = User(
        username=data.username,
        email=data.email,
        full_name=data.full_name,
        password_hash=hash_password(data.password),
        is_active=data.is_active,
        department_id=data.department_id,
        location_id=data.location_id,
        default_business_unit_id=data.default_business_unit_id,
        default_location_id=data.default_location_id,
        default_department_id=data.default_department_id,
    )
    user.roles = roles
    db.add(user)
    db.flush()
    record_audit(db, current_user, "USER_CREATED", "USER", f"Created user {user.username}", entity_id=user.id, after_data={"role_ids": [r.id for r in roles]})
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Username or email is already in use") from exc
    return user_detail(get_editable_user(db, user.id))


@router.get("/roles", response_model=list[RoleSummary])
def list_assignable_roles(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return db.query(Role).options(selectinload(Role.permissions)).order_by(Role.name).all()


@router.get("/departments", response_model=list[DepartmentSummary])
def list_assignable_departments(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return db.query(Department).filter(Department.is_active.is_(True)).order_by(Department.name).all()


@router.get("/locations", response_model=list[LocationSummary])
def list_assignable_locations(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return db.query(Location).filter(Location.is_active.is_(True)).order_by(Location.name).all()


@router.get("/{user_id}", response_model=UserDetailResponse)
def get_user(user_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return user_detail(get_editable_user(db, user_id))


@router.patch("/{user_id}", response_model=UserDetailResponse)
def update_user(user_id: int, data: UserUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    user = get_editable_user(db, user_id)
    changes = data.model_dump(exclude_unset=True)
    for field in ("username", "email", "full_name", "is_active"):
        if field in changes and changes[field] is None:
            raise HTTPException(status_code=422, detail=f"{field} must not be null")
    if user.id == current_user.id and changes.get("is_active") is False and user.is_active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You cannot deactivate your own account")
    if user.id == current_user.id and "username" in changes and changes["username"] != user.username:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You cannot change your own username while signed in; ask another administrator")
    if "username" in changes and db.query(User.id).filter(User.username == changes["username"], User.id != user_id).first():
        raise HTTPException(status_code=409, detail="Username is already in use")
    if "email" in changes and db.query(User.id).filter(User.email == changes["email"], User.id != user_id).first():
        raise HTTPException(status_code=409, detail="Email is already in use")
    if changes.get("department_id") is not None and not db.get(Department, changes["department_id"]):
        raise HTTPException(status_code=422, detail="Department does not exist")
    if changes.get("location_id") is not None and not db.get(Location, changes["location_id"]):
        raise HTTPException(status_code=422, detail="Location does not exist")
    business_unit_id = changes.get("default_business_unit_id", user.default_business_unit_id)
    default_location_id = changes.get("default_location_id", user.default_location_id)
    default_department_id = changes.get("default_department_id", user.default_department_id)
    if business_unit_id:
        from app.models.business_unit import BusinessUnit
        if not db.get(BusinessUnit, business_unit_id):
            raise HTTPException(422, detail="Business Unit does not exist")
        if default_location_id and db.get(Location, default_location_id).business_unit_id != business_unit_id:
            raise HTTPException(422, detail="Default Location does not belong to Business Unit")
        if default_department_id:
            selected_department = db.get(Department, default_department_id)
            if selected_department and selected_department.business_unit_id not in (None, business_unit_id):
                raise HTTPException(422, detail="Default Department does not belong to Business Unit")
    before_data = {field: getattr(user, field) for field in changes}
    for field, value in changes.items():
        setattr(user, field, value)
    after_data = {field: getattr(user, field) for field in changes}
    if changes:
        record_audit(db, current_user, "USER_UPDATED", "USER", f"Updated user {user.username}", entity_id=user.id, before_data=before_data, after_data=after_data)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Username or email is already in use") from exc
    return user_detail(get_editable_user(db, user_id))


@router.put("/{user_id}/roles", response_model=UserDetailResponse)
def replace_user_roles(user_id: int, data: UserRolesUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    user = get_editable_user(db, user_id)
    roles = _validate_roles(db, data.role_ids)
    current_role_ids = {role.id for role in user.roles}
    current_is_admin = is_superuser(user)
    next_is_admin = any(role.name.strip().upper().replace("_", " ") in {"ADMIN", "ADMINISTRATOR", "SYSTEM ADMINISTRATOR", "SUPER ADMIN", "ERP ADMINISTRATOR"} for role in roles)
    if user.id == current_user.id and current_is_admin and not next_is_admin:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You cannot remove your own administrator role")
    if current_role_ids != {role.id for role in roles}:
        before_data = {"role_ids": sorted(current_role_ids)}
        user.roles = roles
        db.flush()
        record_audit(db, current_user, "USER_ROLES_UPDATED", "USER", f"Updated roles for user {user.username}", entity_id=user.id, before_data=before_data, after_data={"role_ids": sorted(role.id for role in roles)})
        db.commit()
    return user_detail(get_editable_user(db, user_id))


@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    user = get_editable_user(db, user_id)
    if user.id == current_user.id:
        raise HTTPException(409, "You cannot delete your own account")
    if is_superuser(user):
        active_admins = [candidate for candidate in editable_user_query(db).filter(User.is_active.is_(True)).all() if is_superuser(candidate)]
        if len(active_admins) <= 1:
            raise HTTPException(409, "The final active administrator cannot be deleted")
    username = user.username
    record_audit(db, current_user, "USER_DELETED", "USER", f"Deleted user {username}", entity_id=user.id)
    db.delete(user)
    db.commit()
