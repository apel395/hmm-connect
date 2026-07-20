from datetime import datetime, timedelta, timezone

from jose import jwt

from passlib.context import CryptContext

from app.core.config import settings

from secrets import token_hex 




pwd_context = CryptContext(
    schemes=["argon2","bcrypt"],
    deprecated="auto"
)



def hash_password(password:str):

    return pwd_context.hash(password)



def verify_password(
    password,
    hashed
):

    return pwd_context.verify(
        password,
        hashed
    )


def create_access_token(user_id: int):

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": str(user_id),
        "type": "access",
        "exp": expire,
    }

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def create_refresh_token(user_id: int):

    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )

    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "exp": expire,
    }

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )