from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token, decode_access_token_claims, hash_password, verify_password
from app.dependencies.auth import get_current_user, oauth2_scheme
from app.models.user import User
from app.schemas.auth import (
    RegistrationRequest,
    RegistrationResponse,
    TokenResponse,
    UserSummary,
)


router = APIRouter(prefix="/auth", tags=["Authentication"])
SESSION_IDLE_TIMEOUT = timedelta(minutes=30)


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


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
    user = (
        db.query(User)
        .filter(User.username == form.username)
        .with_for_update()
        .first()
    )
    if not user or not user.is_active or not verify_password(
        form.password, user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    now = datetime.now(timezone.utc)
    last_activity = _utc(user.session_last_activity_at)
    session_is_active = (
        bool(user.active_session_id)
        and last_activity is not None
        and now - last_activity < SESSION_IDLE_TIMEOUT
    )
    if session_is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This user already has an active session. Log out from the current session or wait until it has been idle for 30 minutes.",
        )

    session_id = str(uuid4())
    user.active_session_id = session_id
    user.session_last_activity_at = now
    db.commit()
    return TokenResponse(access_token=create_access_token(user.username, session_id=session_id))


@router.post("/activity", status_code=204)
def activity(_: User = Depends(get_current_user)):
    # get_current_user validates the session and refreshes server-side activity.
    return None


@router.post("/logout", status_code=204)
def logout(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    # Logout must be able to release a server-side session even when the
    # normal authenticated-user dependency would reject the request first.
    # Decode the presented session directly and clear it only when the token's
    # session id still owns the user's active session. The operation is
    # intentionally idempotent: stale/already-logged-out tokens return 204
    # without affecting a newer active session.
    claims = decode_access_token_claims(token) or {}
    username = claims.get("sub")
    session_id = claims.get("sid")
    if not username or not session_id:
        return None

    user = (
        db.query(User)
        .filter(User.username == username)
        .with_for_update()
        .first()
    )
    if user and user.active_session_id == session_id:
        user.active_session_id = None
        user.session_last_activity_at = None
        db.commit()
    return None


@router.get("/me", response_model=UserSummary)
def current_user(user: User = Depends(get_current_user)):
    return user
