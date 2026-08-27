from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from app.dependencies.auth import get_current_user
from app.models.user import User

# SYSTEM_ADMINISTRATOR is the single canonical unrestricted administrator role.
SUPERUSER_ROLES = frozenset({"SYSTEM_ADMINISTRATOR"})


def normalize_role_name(value: str) -> str:
    return " ".join(value.strip().upper().replace("_", "-").replace("-", " ").split())


def normalize_permission_code(value: str) -> str:
    return value.strip().lower()


def role_names(user: User) -> set[str]:
    return {normalize_role_name(role.name) for role in user.roles}


def effective_role_names(user: User) -> set[str]:
    """Return explicit workflow identities only; authorization comes from permissions."""
    return role_names(user)


def is_superuser(user: User) -> bool:
    roles = role_names(user)
    canonical_admin = normalize_role_name("SYSTEM_ADMINISTRATOR")
    return canonical_admin in roles


def has_any_role(user: User, *allowed_roles: str) -> bool:
    """Role checks are reserved for workflow identity, never API authorization."""
    allowed = {normalize_role_name(role) for role in allowed_roles}
    return is_superuser(user) or bool(role_names(user).intersection(allowed))


def permission_codes(user: User) -> set[str]:
    return {
        normalize_permission_code(permission.code)
        for role in user.roles
        for permission in role.permissions
        if permission.code
    }


def _permission_grants(granted: str, required: str) -> bool:
    if granted == "*" or granted == required:
        return True
    if granted.endswith(".*"):
        return required.startswith(granted[:-1])
    if granted.endswith(".manage"):
        module = granted.removesuffix(".manage")
        return required == f"{module}.view" or required.startswith(f"{module}.")
    return False


def has_permission(user: User, permission_code: str) -> bool:
    if is_superuser(user):
        return True
    required = normalize_permission_code(permission_code)
    return any(_permission_grants(granted, required) for granted in permission_codes(user))


def require_permission(permission_code: str, *legacy_roles: str) -> Callable:
    """Require a persisted Administrator > Roles permission.

    ``legacy_roles`` remains accepted temporarily so already-migrated endpoint
    declarations do not break, but it no longer grants access. This removes the
    old hard-coded role fallback: persisted permission mappings are the sole
    authorization source, except for SYSTEM_ADMINISTRATOR.
    """
    required = normalize_permission_code(permission_code)

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if has_permission(current_user, required):
            return current_user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "INSUFFICIENT_PERMISSION",
                "message": "You are not authorized to perform this action.",
                "required_permission": required,
            },
        )

    return dependency


def require_roles(*allowed_roles: str) -> Callable:
    """Workflow-identity dependency retained for approval/business identity only.

    Operational API endpoints must use ``require_permission`` instead.
    """
    allowed = {normalize_role_name(role) for role in allowed_roles}

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if not has_any_role(current_user, *allowed):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "INSUFFICIENT_WORKFLOW_ROLE",
                    "message": "You are not authorized for this workflow stage.",
                    "required_roles": sorted(allowed),
                },
            )
        return current_user

    return dependency
