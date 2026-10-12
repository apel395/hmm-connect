from fastapi import HTTPException
from sqlalchemy.orm import Query

from app.dependencies.authorization import is_superuser
from app.models.user import User
from app.models.warehouse import Warehouse


def assigned_location_id(user: User) -> int | None:
    """Return the assigned row-level location scope for an operational user."""
    if is_superuser(user):
        return None
    return getattr(user, "default_location_id", None) or getattr(user, "location_id", None)


def apply_location_scope(query: Query, location_column, user: User) -> Query:
    """Restrict a query by the user's location when one is assigned.

    location_column accepts either a SQLAlchemy column or a mapped model for
    backward compatibility with endpoints merged before the centralized API.
    """
    location_id = assigned_location_id(user)
    if location_id is None:
        return query
    column = getattr(location_column, "location_id", location_column)
    if column is None:
        raise RuntimeError("Location scope requires a location column")
    return query.filter(column == location_id)


def require_location_access(document_location_id: int | None, user: User) -> None:
    """Hide documents outside the user's assigned location."""
    assigned = assigned_location_id(user)
    if assigned is not None and document_location_id != assigned:
        raise HTTPException(status_code=404, detail="Document not found")


# Compatibility alias for endpoints already using the previous helper name.
def enforce_location_access(user: User, location_id: int | None) -> None:
    require_location_access(location_id, user)


def resolve_location_id(user: User, requested_location_id: int | None) -> int | None:
    """Force scoped writes to the user's location while preserving unscoped users."""
    assigned = assigned_location_id(user)
    if assigned is None:
        return requested_location_id
    if requested_location_id not in (None, assigned):
        require_location_access(requested_location_id, user)
    return assigned


def apply_warehouse_scope(query: Query, user: User) -> Query:
    location_id = assigned_location_id(user)
    if location_id is None:
        return query
    return query.filter(Warehouse.location_id == location_id)


def enforce_warehouse_access(user: User, warehouse: Warehouse) -> None:
    require_location_access(warehouse.location_id, user)
