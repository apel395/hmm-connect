from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.role import Role
from app.models.user import User
from app.schemas.user import UserResponse


router = APIRouter(prefix="/users", tags=["Users"])


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not any(role.name == "ADMIN" for role in user.roles):
        raise HTTPException(status_code=403, detail="Administrator access required")
    return user


@router.get("", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return (
        db.query(User)
        .options(
            selectinload(User.department),
            selectinload(User.location),
            selectinload(User.roles).selectinload(Role.permissions),
        )
        .order_by(User.username)
        .all()
    )
