from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from app.dependencies.auth import get_current_user
from app.models.user import User

# SYSTEM_ADMINISTRATOR is the single canonical unrestricted administrator role.
SUPERUSER_ROLES = frozenset({"SYSTEM_ADMINISTRATOR"})

# Legacy role implications remain available while endpoints migrate to
# permission dependencies. They are only used when a user has no persisted
# permission mapping, so removing a checkbox from a configured role is enforced.
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


def normalize_permission_code(value: str) -> str:
    return value.strip().lower()


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
    canonical_admin = normalize_role_name("SYSTEM_ADMINISTRATOR")
    return canonical_admin in roles


def has_any_role(user: User, *allowed_roles: str) -> bool:
    allowed = {normalize_role_name(role) for role in allowed_roles}
    return is_superuser(user) or bool(effective_role_names(user).intersection(allowed))


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
    # A module-level manage permission grants its view and action permissions.
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
    """Require a persisted permission, with role fallback for unmigrated users.

    Once any permission is mapped to a user's roles, the persisted mappings are
    authoritative. Legacy fixed-role fallback applies only to users whose roles
    have no permissions yet.
    """
    required = normalize_permission_code(permission_code)

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if has_permission(current_user, required):
            return current_user
        if not permission_codes(current_user) and legacy_roles and has_any_role(current_user, *legacy_roles):
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
