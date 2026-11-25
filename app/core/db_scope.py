"""Stable identifiers for the databases a signed session may address."""

PRIMARY_DB_KEY = "primary"
DEMO_DB_KEY = "demo"
DATABASE_CLAIM = "db"
DATABASE_PARAM = "database_key"
SUPPORTED_DB_KEYS = (PRIMARY_DB_KEY, DEMO_DB_KEY)


def normalize_db_key(value: str | None) -> str:
    """Normalize a trusted database key, failing closed for unknown values."""
    if value in (None, "", PRIMARY_DB_KEY):
        return PRIMARY_DB_KEY
    if value == DEMO_DB_KEY:
        return DEMO_DB_KEY
    raise ValueError(f"Unsupported database key: {value}")
