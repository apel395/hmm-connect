from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy.orm import Session

from app.core.database import get_db

from app.dependencies.auth import get_current_user

from app.models.role import Role
from app.services.audit import record_audit

from app.schemas.role import (
    RoleCreate,
    RoleResponse,
    RoleUpdate,
)


router = APIRouter(
    prefix="/roles",
    tags=["Roles"],
)


@router.get(
    "",
    response_model=list[RoleResponse],
)
def get_roles(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return db.query(Role).order_by(Role.id).all()


@router.post(
    "",
    response_model=RoleResponse,
    status_code=201,
)
def create_role(
    data: RoleCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    existing_role = (
        db.query(Role)
        .filter(Role.name == data.name)
        .first()
    )

    if existing_role:
        raise HTTPException(
            status_code=409,
            detail="Role already exists",
        )

    role = Role(
        name=data.name,
        description=data.description,
    )

    db.add(role)
    db.flush()

    record_audit(
        db=db,
        user=current_user,
        action="CREATE",
        entity_type="ROLE",
        entity_id=role.id,
        summary=f"Created role {role.name}",
        details={"name": role.name},
    )

    db.commit()
    db.refresh(role)

    return role


@router.patch(
    "/{role_id}",
    response_model=RoleResponse,
)
def update_role(
    role_id: int,
    data: RoleUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    before = {"name": role.name, "description": role.description}

    if data.name is not None:
        name = data.name.strip()
        duplicate = (
            db.query(Role)
            .filter(Role.name == name, Role.id != role.id)
            .first()
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="Role already exists")
        role.name = name
    if data.description is not None:
        role.description = data.description.strip() or None

    record_audit(
        db=db,
        user=current_user,
        action="UPDATE",
        entity_type="ROLE",
        entity_id=role.id,
        summary=f"Updated role {role.name}",
        details={"before": before, "after": {"name": role.name, "description": role.description}},
    )

    db.commit()
    db.refresh(role)
    return role


@router.delete(
    "/{role_id}",
    status_code=204,
)
def delete_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    role = (
        db.query(Role)
        .filter(Role.id == role_id)
        .first()
    )

    if not role:
        raise HTTPException(
            status_code=404,
            detail="Role not found",
        )

    record_audit(
        db=db,
        user=current_user,
        action="DELETE",
        entity_type="ROLE",
        entity_id=role.id,
        summary=f"Deleted role {role.name}",
        details={"name": role.name},
    )

    db.delete(role)
    db.commit()