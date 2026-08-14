from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import is_superuser
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User
from app.services.audit import record_audit

router = APIRouter(prefix="/roles", tags=["Roles"])

CORE_ROLE_PERMISSIONS = {
    "SYSTEM_ADMINISTRATOR": ["*"],
    "GENERAL_MANAGER": ["dashboard.view", "reports.view", "purchasing.view", "inventory.view", "finance.view", "approval.final"],
    "PURCHASING": ["dashboard.view", "products.view", "suppliers.manage", "pr.manage", "po.manage", "receiving.manage", "inventory.view", "reports.purchasing"],
    "WAREHOUSE": ["dashboard.view", "warehouse.manage", "receiving.manage", "inventory.manage", "purchasing.view", "reports.inventory"],
    "FINANCE": ["dashboard.view", "finance.manage", "ap.manage", "supplier_invoice.manage", "payment.manage", "journal.manage", "coa.manage", "reports.finance", "purchasing.view"],
    "DEPARTMENT": ["dashboard.view", "pr.own.manage", "reports.own"],
    "AUDITOR": ["dashboard.view", "audit.read", "reports.view", "purchasing.view", "inventory.view", "finance.view"],
    "VIEWER": ["dashboard.view", "reports.view"],
}

CORE_ROLE_DESCRIPTIONS = {
    "SYSTEM_ADMINISTRATOR": "Full system administration and unrestricted operational access.",
    "GENERAL_MANAGER": "Executive monitoring and final approval access.",
    "PURCHASING": "Purchase requisition, purchase order, supplier, and receiving operations.",
    "WAREHOUSE": "Receiving and inventory operations.",
    "FINANCE": "Accounts payable, supplier invoices, payments, journals, and finance reporting.",
    "DEPARTMENT": "Department purchasing requester with own-scope access.",
    "AUDITOR": "Read-only audit and cross-module reporting access.",
    "VIEWER": "Read-only dashboard and reporting access.",
}


class RoleInput(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=200)
    permission_codes: list[str] = Field(default_factory=list)


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not is_superuser(user):
        raise HTTPException(403, "Administrator access required")
    return user


def _ensure_permission(db: Session, code: str) -> Permission:
    permission = db.query(Permission).filter(Permission.code == code).first()
    if not permission:
        permission = Permission(code=code, description=code.replace(".", " ").replace("_", " ").title())
        db.add(permission)
        db.flush()
    return permission


def _ensure_core_roles(db: Session) -> None:
    changed = False
    for name, codes in CORE_ROLE_PERMISSIONS.items():
        role = db.query(Role).options(selectinload(Role.permissions)).filter(Role.name == name).first()
        if not role:
            role = Role(name=name, description=CORE_ROLE_DESCRIPTIONS[name])
            db.add(role)
            db.flush()
            changed = True
        if not role.description:
            role.description = CORE_ROLE_DESCRIPTIONS[name]
            changed = True
        desired = [_ensure_permission(db, code) for code in codes]
        desired_ids = {item.id for item in desired}
        if {item.id for item in role.permissions} != desired_ids:
            role.permissions = desired
            changed = True
    if changed:
        db.commit()


def serialize(role: Role) -> dict:
    return {
        "id": role.id,
        "name": role.name,
        "description": role.description,
        "permissions": [
            {"id": p.id, "code": p.code, "description": p.description}
            for p in sorted(role.permissions, key=lambda value: value.code)
        ],
        "user_count": len(role.users),
    }


@router.get("")
def list_roles(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    _ensure_core_roles(db)
    roles = db.query(Role).options(selectinload(Role.permissions), selectinload(Role.users)).order_by(Role.name).all()
    return [serialize(role) for role in roles]


@router.get("/permissions")
def list_permissions(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    _ensure_core_roles(db)
    return [
        {"id": item.id, "code": item.code, "description": item.description}
        for item in db.query(Permission).order_by(Permission.code).all()
    ]


@router.post("", status_code=201)
def create_role(data: RoleInput, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    name = data.name.strip().upper().replace(" ", "_")
    if db.query(Role).filter(Role.name == name).first():
        raise HTTPException(409, "Role already exists")
    role = Role(name=name, description=data.description)
    role.permissions = [_ensure_permission(db, code.strip()) for code in dict.fromkeys(data.permission_codes) if code.strip()]
    db.add(role)
    db.flush()
    record_audit(db, user, "ROLE_CREATED", "ROLE", f"Created role {name}", entity_id=role.id)
    db.commit()
    db.refresh(role)
    return serialize(db.query(Role).options(selectinload(Role.permissions), selectinload(Role.users)).get(role.id))


@router.put("/{role_id}")
def update_role(role_id: int, data: RoleInput, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    role = db.query(Role).options(selectinload(Role.permissions), selectinload(Role.users)).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(404, "Role not found")
    name = data.name.strip().upper().replace(" ", "_")
    duplicate = db.query(Role).filter(Role.name == name, Role.id != role_id).first()
    if duplicate:
        raise HTTPException(409, "Role already exists")
    before = {"name": role.name, "description": role.description, "permission_codes": [p.code for p in role.permissions]}
    role.name = name
    role.description = data.description
    role.permissions = [_ensure_permission(db, code.strip()) for code in dict.fromkeys(data.permission_codes) if code.strip()]
    record_audit(db, user, "ROLE_UPDATED", "ROLE", f"Updated role {name}", entity_id=role.id, before_data=before, after_data={"name": name, "description": data.description, "permission_codes": data.permission_codes})
    db.commit()
    return serialize(db.query(Role).options(selectinload(Role.permissions), selectinload(Role.users)).filter(Role.id == role_id).first())


@router.delete("/{role_id}", status_code=204)
def delete_role(role_id: int, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    role = db.query(Role).options(selectinload(Role.users)).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(404, "Role not found")
    if role.name == "SYSTEM_ADMINISTRATOR":
        raise HTTPException(409, "SYSTEM_ADMINISTRATOR cannot be deleted")
    if role.users:
        raise HTTPException(409, "Role is assigned to users and cannot be deleted")
    name = role.name
    record_audit(db, user, "ROLE_DELETED", "ROLE", f"Deleted role {name}", entity_id=role.id)
    db.delete(role)
    db.commit()
