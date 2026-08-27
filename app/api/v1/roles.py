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

PERMISSION_CATALOG = {
    "dashboard.view",
    "approval.view", "approval.manage",
    "products.view", "products.manage",
    "suppliers.view", "suppliers.manage",
    "warehouse.view", "warehouse.manage",
    "pr.view", "pr.create", "pr.edit", "pr.submit", "pr.approve", "pr.convert", "pr.manage",
    "market_list.view", "market_list.create", "market_list.edit", "market_list.submit", "market_list.approve", "market_list.convert", "market_list.manage",
    "po.view", "po.create", "po.edit", "po.submit", "po.approve", "po.manage",
    "receiving.view", "receiving.manage",
    "inventory.view", "inventory.manage",
    "store_request.view", "store_request.manage",
    "stock_opname.view", "stock_opname.manage",
    "finance.view", "finance.manage",
    "ap.view", "ap.manage",
    "supplier_invoice.view", "supplier_invoice.create", "supplier_invoice.edit",
    "supplier_invoice.verify", "supplier_invoice.reject", "supplier_invoice.post",
    "supplier_invoice.void", "supplier_invoice.manage",
    "payment.view", "payment.manage",
    "journal.view", "journal.manage",
    "coa.view", "coa.manage",
    "reports.view", "reports.purchasing", "reports.inventory", "reports.finance", "reports.own",
    "audit.read",
    "admin.users.manage", "admin.roles.manage", "admin.settings.manage",
}

CORE_ROLE_NAMES = {
    "SYSTEM_ADMINISTRATOR",
    "GENERAL_MANAGER",
    "PURCHASING",
    "WAREHOUSE",
    "FINANCE",
    "DEPARTMENT",
    "AUDITOR",
    "VIEWER",
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
    """Bootstrap catalog and missing core roles; never overwrite role mappings."""
    for code in sorted(PERMISSION_CATALOG):
        _ensure_permission(db, code)
    for name in sorted(CORE_ROLE_NAMES):
        role = db.query(Role).filter(Role.name == name).first()
        if not role:
            db.add(Role(name=name, description=CORE_ROLE_DESCRIPTIONS[name]))
    db.commit()


def _resolve_permissions(db: Session, codes: list[str]) -> list[Permission]:
    normalized = list(dict.fromkeys(code.strip() for code in codes if code.strip()))
    if not normalized:
        return []
    rows = db.query(Permission).filter(Permission.code.in_(normalized)).all()
    by_code = {row.code: row for row in rows}
    missing = [code for code in normalized if code not in by_code]
    if missing:
        raise HTTPException(400, "Unknown permission code(s): " + ", ".join(missing))
    return [by_code[code] for code in normalized]


def serialize(role: Role) -> dict:
    return {
        "id": role.id,
        "name": role.name,
        "description": role.description,
        "permissions": [{"id": p.id, "code": p.code, "description": p.description} for p in sorted(role.permissions, key=lambda value: value.code)],
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
    return [{"id": item.id, "code": item.code, "description": item.description} for item in db.query(Permission).order_by(Permission.code).all()]


@router.post("", status_code=201)
def create_role(data: RoleInput, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    name = data.name.strip().upper().replace(" ", "_")
    if db.query(Role).filter(Role.name == name).first():
        raise HTTPException(409, "Role already exists")
    role = Role(name=name, description=data.description)
    role.permissions = _resolve_permissions(db, data.permission_codes)
    db.add(role)
    db.flush()
    record_audit(db, user, "ROLE_CREATED", "ROLE", f"Created role {name}", entity_id=role.id)
    db.commit()
    return serialize(db.query(Role).options(selectinload(Role.permissions), selectinload(Role.users)).filter(Role.id == role.id).first())


@router.put("/{role_id}")
@router.patch("/{role_id}")
def update_role(role_id: int, data: RoleInput, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    role = db.query(Role).options(selectinload(Role.permissions), selectinload(Role.users)).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(404, "Role not found")
    original_name = role.name
    name = data.name.strip().upper().replace(" ", "_")
    if original_name in CORE_ROLE_NAMES and name != original_name:
        raise HTTPException(409, "Core role names cannot be changed")
    duplicate = db.query(Role).filter(Role.name == name, Role.id != role_id).first()
    if duplicate:
        raise HTTPException(409, "Role already exists")
    permissions = _resolve_permissions(db, data.permission_codes)
    before = {"name": role.name, "description": role.description, "permission_codes": [p.code for p in role.permissions]}
    role.name = name
    role.description = data.description
    role.permissions = permissions
    record_audit(db, user, "ROLE_UPDATED", "ROLE", f"Updated role {name}", entity_id=role.id, before_data=before, after_data={"name": name, "description": data.description, "permission_codes": [p.code for p in permissions]})
    db.commit()
    return serialize(db.query(Role).options(selectinload(Role.permissions), selectinload(Role.users)).filter(Role.id == role_id).first())


@router.delete("/{role_id}", status_code=204)
def delete_role(role_id: int, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    role = db.query(Role).options(selectinload(Role.users)).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(404, "Role not found")
    if role.name in CORE_ROLE_NAMES:
        raise HTTPException(409, "Core roles cannot be deleted")
    if role.users:
        raise HTTPException(409, "Role is assigned to users and cannot be deleted")
    name = role.name
    record_audit(db, user, "ROLE_DELETED", "ROLE", f"Deleted role {name}", entity_id=role.id)
    db.delete(role)
    db.commit()
