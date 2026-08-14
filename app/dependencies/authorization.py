from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from app.dependencies.auth import get_current_user
from app.models.user import User

SUPERUSER_ROLES = frozenset({
    "ADMIN",
    "ADMINISTRATOR",
    "SYSTEM ADMIN",
    "SYSTEM ADMINISTRATOR",
    "SYSTEM_ADMIN",
    "SYSTEM_ADMINISTRATOR",
    "SUPER ADMIN",
    "SUPER_ADMIN",
    "SUPERUSER",
    "ERP ADMIN",
    "ERP ADMINISTRATOR",
    "ERP_ADMIN",
    "ERP_ADMINISTRATOR",
})

# Canonical HMM-Connect roles can satisfy legacy endpoint role checks while we
# progressively migrate individual APIs to permission-based authorization.
ROLE_IMPLICATIONS = {
    "PURCHASING": {"PURCHASING", "REQUESTER"},
    "WAREHOUSE": {"WAREHOUSE"},
    "FINANCE": {"FINANCE"},
    "DEPARTMENT": {"DEPARTMENT", "REQUESTER"},
    "GENERAL MANAGER": {"GENERAL MANAGER"},
    "AUDITOR": {"AUDITOR"},
    "VIEWER": {"VIEWER"},
}


def normalize_role_name(value: str) -> str:
    return " ".join(value.strip().upper().replace("_", "-").replace("-", " ").split())


def role_names(user: User) -> set[str]:
    return {normalize_role_name(role.name) for role in user.roles}


def effective_role_names(user: User) -> set[str]:
    names = role_names(user)
    effective = set(names)
    for role in names:
        effective.update(ROLE_IMPLICATIONS.get(role, set()))
    return {normalize_role_name(role) for role in effective}


def is_superuser(user: User) -> bool:
    roles = role_names(user)
    normalized_superusers = {normalize_role_name(role) for role in SUPERUSER_ROLES}
    return bool(roles.intersection(normalized_superusers)) or any(
        role == "ADMIN" or role.endswith(" ADMIN") or role.endswith(" ADMINISTRATOR")
        for role in roles
    )


def has_any_role(user: User, *allowed_roles: str) -> bool:
    allowed = {normalize_role_name(role) for role in allowed_roles}
    return is_superuser(user) or bool(effective_role_names(user).intersection(allowed))


def has_permission(user: User, permission_code: str) -> bool:
    if is_superuser(user):
        return True
    return any(
        permission.code == permission_code or permission.code == "*"
        for role in user.roles
        for permission in role.permissions
    )


def require_roles(*allowed_roles: str) -> Callable:
    allowed = {normalize_role_name(role) for role in allowed_roles}

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if not has_any_role(current_user, *allowed):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "INSUFFICIENT_PERMISSION",
                    "message": "You are not authorized to perform this action.",
                    "required_roles": sorted(allowed),
                },
            )
        return current_user

    return dependency
