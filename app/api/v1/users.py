from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.department import Department
from app.models.location import Location
from app.models.role import Role
from app.models.user import User
from app.schemas.auth import RoleSummary
from app.schemas.user import (
    DepartmentSummary,
    LocationSummary,
    UserDetailResponse,
    UserResponse,
    UserRolesUpdate,
    UserUpdate,
)
from app.services.audit import record_audit


router = APIRouter(prefix="/users", tags=["Users"])


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not any(role.name.upper() == "ADMIN" for role in user.roles):
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


@router.get("", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return (
        editable_user_query(db)
        .order_by(User.username)
        .all()
    )


@router.get("/roles", response_model=list[RoleSummary])
def list_assignable_roles(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return (
        db.query(Role)
        .options(selectinload(Role.permissions))
        .order_by(Role.name)
        .all()
    )


@router.get("/departments", response_model=list[DepartmentSummary])
def list_assignable_departments(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return (
        db.query(Department)
        .filter(Department.is_active.is_(True))
        .order_by(Department.name)
        .all()
    )


@router.get("/locations", response_model=list[LocationSummary])
def list_assignable_locations(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return (
        db.query(Location)
        .filter(Location.is_active.is_(True))
        .order_by(Location.name)
        .all()
    )


@router.get("/{user_id}", response_model=UserDetailResponse)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return user_detail(get_editable_user(db, user_id))


@router.patch("/{user_id}", response_model=UserDetailResponse)
def update_user(
    user_id: int,
    data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = get_editable_user(db, user_id)
    changes = data.model_dump(exclude_unset=True)

    for field in ("username", "email", "full_name", "is_active"):
        if field in changes and changes[field] is None:
            raise HTTPException(
                status_code=422,
                detail=f"{field} must not be null",
            )

    if (
        user.id == current_user.id
        and changes.get("is_active") is False
        and user.is_active
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You cannot deactivate your own account",
        )

    if (
        user.id == current_user.id
        and "username" in changes
        and changes["username"] != user.username
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "You cannot change your own username while signed in; "
                "ask another administrator"
            ),
        )

    if "username" in changes:
        duplicate = (
            db.query(User.id)
            .filter(User.username == changes["username"], User.id != user_id)
            .first()
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="Username is already in use")

    if "email" in changes:
        duplicate = (
            db.query(User.id)
            .filter(User.email == changes["email"], User.id != user_id)
            .first()
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="Email is already in use")

    if changes.get("department_id") is not None:
        department = db.get(Department, changes["department_id"])
        if not department:
            raise HTTPException(status_code=422, detail="Department does not exist")

    if changes.get("location_id") is not None:
        location = db.get(Location, changes["location_id"])
        if not location:
            raise HTTPException(status_code=422, detail="Location does not exist")
    business_unit_id=changes.get("default_business_unit_id",user.default_business_unit_id)
    default_location_id=changes.get("default_location_id",user.default_location_id)
    default_department_id=changes.get("default_department_id",user.default_department_id)
    if business_unit_id:
        from app.models.business_unit import BusinessUnit
        if not db.get(BusinessUnit,business_unit_id):raise HTTPException(422,detail="Business Unit does not exist")
        if default_location_id and db.get(Location,default_location_id).business_unit_id!=business_unit_id:raise HTTPException(422,detail="Default Location does not belong to Business Unit")
        if default_department_id:
            selected_department=db.get(Department,default_department_id)
            if selected_department and selected_department.business_unit_id not in (None,business_unit_id):raise HTTPException(422,detail="Default Department does not belong to Business Unit")

    before_data = {
        field: getattr(user, field)
        for field in changes
    }
    for field, value in changes.items():
        setattr(user, field, value)
    after_data = {
        field: getattr(user, field)
        for field in changes
    }

    if changes:
        record_audit(
            db,
            current_user,
            "USER_UPDATED",
            "USER",
            f"Updated user {user.username}",
            entity_id=user.id,
            before_data=before_data,
            after_data=after_data,
        )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Username or email is already in use",
        ) from exc

    return user_detail(get_editable_user(db, user_id))


@router.put("/{user_id}/roles", response_model=UserDetailResponse)
def replace_user_roles(
    user_id: int,
    data: UserRolesUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = get_editable_user(db, user_id)
    roles = (
        db.query(Role)
        .options(selectinload(Role.permissions))
        .filter(Role.id.in_(data.role_ids))
        .all()
        if data.role_ids
        else []
    )
    found_role_ids = {role.id for role in roles}
    missing_role_ids = sorted(set(data.role_ids) - found_role_ids)
    if missing_role_ids:
        raise HTTPException(
            status_code=422,
            detail={"message": "One or more roles do not exist", "role_ids": missing_role_ids},
        )

    current_role_ids = {role.id for role in user.roles}
    current_is_admin = any(role.name.upper() == "ADMIN" for role in user.roles)
    next_is_admin = any(role.name.upper() == "ADMIN" for role in roles)

    if user.id == current_user.id and current_is_admin and not next_is_admin:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You cannot remove your own administrator role",
        )

    if current_is_admin and user.is_active and not next_is_admin:
        active_admin_count = (
            db.query(func.count(User.id))
            .join(User.roles)
            .filter(
                User.is_active.is_(True),
                func.upper(Role.name) == "ADMIN",
            )
            .scalar()
        )
        if active_admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The final active administrator role cannot be removed",
            )

    if current_role_ids != found_role_ids:
        before_data = {"role_ids": sorted(current_role_ids)}
        user.roles = roles
        db.flush()
        record_audit(
            db,
            current_user,
            "USER_ROLES_UPDATED",
            "USER",
            f"Updated roles for user {user.username}",
            entity_id=user.id,
            before_data=before_data,
            after_data={"role_ids": sorted(found_role_ids)},
        )
        db.commit()

    return user_detail(get_editable_user(db, user_id))
