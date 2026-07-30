from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.auth import (
    RegistrationRequest,
    RegistrationResponse,
    TokenResponse,
    UserSummary,
)


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=RegistrationResponse, status_code=201)
def register(
    data: RegistrationRequest,
    db: Session = Depends(get_db),
):
    username_exists = (
        db.query(User.id)
        .filter(User.username == data.username)
        .first()
    )
    if username_exists:
        raise HTTPException(status_code=409, detail="Username is already registered")

    email_exists = (
        db.query(User.id)
        .filter(User.email == data.email)
        .first()
    )
    if email_exists:
        raise HTTPException(status_code=409, detail="Email is already registered")

    user = User(
        username=data.username,
        full_name=data.full_name,
        email=data.email,
        password_hash=hash_password(data.password),
        is_active=True,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Username or email is already registered",
        ) from exc
    db.refresh(user)

    return RegistrationResponse(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        email=user.email,
        is_active=user.is_active,
        requires_admin_access=True,
        message=(
            "Your account has been created and is waiting for "
            "administrator access."
        ),
    )


@router.post("/login", response_model=TokenResponse)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == form.username).first()
    if not user or not user.is_active or not verify_password(
        form.password, user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    return TokenResponse(access_token=create_access_token(user.username))


@router.get("/me", response_model=UserSummary)
def current_user(user: User = Depends(get_current_user)):
    return user
