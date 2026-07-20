from fastapi import APIRouter
from fastapi import Depends
from fastapi import status
from fastapi import HTTPException

from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db

from app.schemas.auth import LoginRequest
from app.schemas.auth import RegisterRequest
from app.schemas.auth import TokenResponse

from app.schemas.user import UserResponse

from app.repositories.user_repository import UserRepository

from app.services.auth_service import AuthService
from app.services.audit import record_audit
from app.dependencies.auth import get_current_user
from app.models.user import User


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/login",
    response_model=TokenResponse,
)
def login(
    data: LoginRequest,
    db: Session = Depends(get_db),
):
    repository = UserRepository(db)
    service = AuthService(repository)

    result = service.login(
        data.username,
        data.password,
    )

    user = (
        db.query(User)
        .options(
            joinedload(User.department),
            joinedload(User.location),
            joinedload(User.roles),
        )
        .filter(User.username == data.username.strip())
        .first()
    )

    if user:
        record_audit(
            db=db,
            user=user,
            action="LOGIN",
            entity_type="USER",
            entity_id=user.id,
            summary=f"User {user.username} logged in",
        )
        db.commit()

    return result


@router.get(
    "/me",
    response_model=UserResponse,
)
def me(
    current_user: User = Depends(get_current_user),
):
    return current_user


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    data: RegisterRequest,
    db: Session = Depends(get_db),
):
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Public registration is disabled. Ask an administrator to create your user.",
    )

    repository = UserRepository(db)
    service = AuthService(repository)

    return service.register(
        data.username,
        data.email,
        data.full_name,
        data.password,
    )
