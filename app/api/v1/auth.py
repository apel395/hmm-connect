from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Form, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_database_key, get_db, session_factory_for, session_for
from app.core.db_scope import DEMO_DB_KEY, PRIMARY_DB_KEY
from app.core.security import create_access_token, decode_access_token_claims, hash_password, verify_password
from app.dependencies.auth import get_current_user, oauth2_scheme
from app.dependencies.authorization import is_superuser
from app.models.user import User
from app.models.location_department import LocationDepartment
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


def _user_summary(db: Session, user: User) -> UserSummary:
    resolved_location = user.default_location or user.location
    resolved_department = user.default_department or user.department

    if resolved_location:
        resolved_business_unit_id = resolved_location.business_unit_id
    elif resolved_department and resolved_department.business_unit_id is not None:
        resolved_business_unit_id = resolved_department.business_unit_id
    else:
        resolved_business_unit_id = user.default_business_unit_id

    resolved_department_id = user.default_department_id or user.department_id
    if resolved_department and resolved_business_unit_id is not None:
        invalid_business_unit = resolved_department.business_unit_id not in {None, resolved_business_unit_id}
        invalid_location = False
        if resolved_location and not invalid_business_unit:
            invalid_location = (
                db.query(LocationDepartment)
                .filter(
                    LocationDepartment.location_id == resolved_location.id,
                    LocationDepartment.department_id == resolved_department.id,
                )
                .first()
                is None
            )
        if invalid_business_unit or invalid_location:
            resolved_department_id = None

    return UserSummary(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        business_unit_id=resolved_business_unit_id,
        department_id=resolved_department_id,
        location_id=user.default_location_id or user.location_id,
        default_business_unit_id=user.default_business_unit_id,
        default_department_id=user.default_department_id,
        default_location_id=user.default_location_id,
        roles=user.roles,
    )


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


def _login_database_key(username: str) -> str:
    if username not in settings.demo_usernames:
        return PRIMARY_DB_KEY
    # Fail closed: a configured demo account must never authenticate against
    # the primary database when the demo database is missing.
    session_factory_for(DEMO_DB_KEY)
    return DEMO_DB_KEY


def _login(
    form: OAuth2PasswordRequestForm,
    db: Session,
    database_key: str,
    replace_session: bool,
) -> TokenResponse:
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
    # Administrator sign-in always takes over after credentials are verified.
    if session_is_active and not (replace_session or is_superuser(user)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This account has an active session. You can sign in and end the previous session if you were disconnected.",
        )

    session_id = str(uuid4())
    # Prepare the response before persisting a session the client cannot use.
    response = TokenResponse(
        access_token=create_access_token(
            user.username,
            session_id=session_id,
            database_key=database_key,
        ),
        user=_user_summary(db, user),
    )
    user.active_session_id = session_id
    user.session_last_activity_at = now
    db.commit()
    return response


@router.post("/login", response_model=TokenResponse)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
    replace_session: Annotated[bool, Form()] = False,
):
    database_key = _login_database_key(form.username)
    if database_key == PRIMARY_DB_KEY:
        return _login(form, db, database_key, replace_session)

    # The primary `get_db` dependency keeps existing test overrides working;
    # demo accounts authenticate only against the allowlisted demo database.
    with session_for(database_key) as demo_db:
        return _login(form, demo_db, database_key, replace_session)


@router.post("/activity", status_code=204)
def activity(_: User = Depends(get_current_user)):
    return None


@router.post("/logout", status_code=204)
def logout(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
    _: str = Depends(get_database_key),
):
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
def current_user(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _user_summary(db, user)
