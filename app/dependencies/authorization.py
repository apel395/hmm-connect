from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from app.dependencies.auth import get_current_user
from app.models.user import User

SUPERUSER_ROLES = frozenset({"ADMIN", "ADMINISTRATOR", "SUPER_ADMIN"})


def role_names(user: User) -> set[str]:
    """Return normalized role names for authoritative access checks."""
    return {role.name.strip().upper() for role in user.roles}


def is_superuser(user: User) -> bool:
    return bool(role_names(user).intersection(SUPERUSER_ROLES))


def has_any_role(user: User, *allowed_roles: str) -> bool:
    allowed = {role.strip().upper() for role in allowed_roles}
    return is_superuser(user) or bool(role_names(user).intersection(allowed))


def require_roles(*allowed_roles: str) -> Callable:
    allowed = {role.upper() for role in allowed_roles}

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
