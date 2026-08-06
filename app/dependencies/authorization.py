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


def normalize_role_name(value: str) -> str:
    return " ".join(value.strip().upper().replace("_", "-").replace("-", " ").split())


def role_names(user: User) -> set[str]:
    """Return normalized role names for authoritative access checks."""
    return {normalize_role_name(role.name) for role in user.roles}


def is_superuser(user: User) -> bool:
    roles = role_names(user)
    normalized_superusers = {normalize_role_name(role) for role in SUPERUSER_ROLES}
    return bool(roles.intersection(normalized_superusers)) or any(
        role == "ADMIN" or role.endswith(" ADMIN") or role.endswith(" ADMINISTRATOR")
        for role in roles
    )


def has_any_role(user: User, *allowed_roles: str) -> bool:
    allowed = {normalize_role_name(role) for role in allowed_roles}
    return is_superuser(user) or bool(role_names(user).intersection(allowed))


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
