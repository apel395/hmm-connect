import os

from fastapi import HTTPException, Request
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.db_scope import (
    DATABASE_CLAIM,
    DEMO_DB_KEY,
    PRIMARY_DB_KEY,
    normalize_db_key,
)
from app.core.security import decode_access_token_claims


DATABASE_URL = settings.DATABASE_URL or (
    f"postgresql://"
    f"{settings.DB_USER}:"
    f"{settings.DB_PASSWORD}@"
    f"{settings.DB_HOST}:"
    f"{settings.DB_PORT}/"
    f"{settings.DB_NAME}"
)

engine_options: dict[str, object] = {
    "pool_pre_ping": True,
    "future": True,
}

if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
    engine_options["poolclass"] = NullPool
    engine_options["connect_args"] = {"connect_timeout": 5}


Engines: dict[str, Engine] = {}
SessionFactories: dict[str, sessionmaker[Session]] = {}


def register_database(key: str, url: str) -> sessionmaker[Session]:
    """Register an allowlisted database URL and return its session factory."""
    normalized = normalize_db_key(key)
    if normalized == DEMO_DB_KEY and url == DATABASE_URL:
        raise RuntimeError("DEMO_DATABASE_URL must not point at the primary database")

    engine = create_engine(url, **engine_options)
    factory = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    Engines[normalized] = engine
    SessionFactories[normalized] = factory
    return factory


register_database(PRIMARY_DB_KEY, DATABASE_URL)
if settings.DEMO_DATABASE_URL:
    register_database(DEMO_DB_KEY, settings.DEMO_DATABASE_URL)

# Backwards-compatible aliases for scripts and older imports.
engine = Engines[PRIMARY_DB_KEY]
SessionLocal = SessionFactories[PRIMARY_DB_KEY]


def session_factory_for(key: str | None) -> sessionmaker[Session]:
    normalized = normalize_db_key(key)
    try:
        return SessionFactories[normalized]
    except KeyError as exc:
        if normalized == DEMO_DB_KEY:
            raise HTTPException(
                status_code=503,
                detail="Demo database is not configured",
            ) from exc
        raise


def session_for(key: str | None) -> Session:
    return session_factory_for(key)()


def known_database_keys() -> tuple[str, ...]:
    return tuple(key for key in (PRIMARY_DB_KEY, DEMO_DB_KEY) if key in SessionFactories)


def database_key_from_claims(claims: dict | None) -> str:
    raw_key = claims.get(DATABASE_CLAIM) if claims else None
    try:
        key = normalize_db_key(raw_key)
    except ValueError as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid database scope in session",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return key


def database_key_from_request(request: Request) -> str:
    authorization = request.headers.get("Authorization", "")
    if not authorization.lower().startswith("bearer "):
        return PRIMARY_DB_KEY

    token = authorization.split(None, 1)[1].strip()
    return database_key_from_claims(decode_access_token_claims(token))


def get_database_key(request: Request) -> str:
    """Resolve the signed database scope for the current request."""
    key = database_key_from_request(request)
    session_factory_for(key)
    return key


def get_db(request: Request):
    db = session_for(database_key_from_request(request))
    try:
        yield db
    finally:
        db.close()
