from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from app.dependencies.auth import get_current_user
from app.models.user import User


def require_roles(*allowed_roles: str) -> Callable:
    allowed = {role.upper() for role in allowed_roles}

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        user_roles = {role.name.upper() for role in current_user.roles}
        if not user_roles.intersection(allowed):
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
