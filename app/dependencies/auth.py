from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token_claims
from app.models.user import User


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
SESSION_IDLE_TIMEOUT = timedelta(minutes=30)
ACTIVITY_WRITE_INTERVAL = timedelta(minutes=1)


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    claims = decode_access_token_claims(token)
    username = claims.get("sub") if claims else None
    session_id = claims.get("sid") if claims else None
    if not username or not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = (
        db.query(User)
        .filter(User.username == username, User.is_active.is_(True))
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is inactive or no longer exists",
        )

    now = datetime.now(timezone.utc)
    last_activity = _utc(user.session_last_activity_at)
    if user.active_session_id != session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session is no longer active",
        )
    if last_activity is None or now - last_activity >= SESSION_IDLE_TIMEOUT:
        user.active_session_id = None
        user.session_last_activity_at = None
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired after 30 minutes of inactivity",
        )

    if now - last_activity >= ACTIVITY_WRITE_INTERVAL:
        user.session_last_activity_at = now
        db.commit()
        db.refresh(user)

    return user
