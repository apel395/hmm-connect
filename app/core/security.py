from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings


password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, password_hash: str) -> bool:
    return password_context.verify(plain_password, password_hash)


def hash_password(password: str) -> str:
    return password_context.hash(password)


def create_access_token(subject: str, session_id: str | None = None) -> str:
    expiry_minutes = (
        settings.SESSION_ACCESS_TOKEN_EXPIRE_MINUTES
        if session_id
        else settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=expiry_minutes)
    payload = {"sub": subject, "exp": expires_at}
    if session_id:
        payload["sid"] = session_id
    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def decode_access_token_claims(token: str) -> dict | None:
    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
    except JWTError:
        return None


def decode_access_token(token: str) -> str | None:
    payload = decode_access_token_claims(token)
    return payload.get("sub") if payload else None
