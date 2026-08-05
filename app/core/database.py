import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings


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

engine = create_engine(DATABASE_URL, **engine_options)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db():
    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()
