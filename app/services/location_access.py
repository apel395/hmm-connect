from fastapi import HTTPException
from sqlalchemy.orm import Query

from app.dependencies.authorization import is_superuser
from app.models.user import User
from app.models.warehouse import Warehouse


def assigned_location_id(user: User) -> int | None:
    """Return the hard row-level location scope for an operational user."""
    if is_superuser(user):
        return None
    return user.default_location_id or user.location_id


def apply_location_scope(query: Query, model, user: User) -> Query:
    """Restrict a model query when the signed-in user has a work location."""
    location_id = assigned_location_id(user)
    if location_id is None:
        return query
    column = getattr(model, "location_id", None)
    if column is None:
        raise RuntimeError(f"{model.__name__} does not expose location_id")
    return query.filter(column == location_id)


def enforce_location_access(user: User, location_id: int | None) -> None:
    """Reject cross-location detail access and writes."""
    assigned = assigned_location_id(user)
    if assigned is not None and location_id != assigned:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "LOCATION_ACCESS_DENIED",
                "message": "This record is outside your assigned work location.",
                "assigned_location_id": assigned,
            },
        )


def resolve_location_id(user: User, requested_location_id: int | None) -> int | None:
    """Force scoped writes to the user's work location."""
    assigned = assigned_location_id(user)
    if assigned is None:
        return requested_location_id
    if requested_location_id not in (None, assigned):
        enforce_location_access(user, requested_location_id)
    return assigned


def apply_warehouse_scope(query: Query, user: User) -> Query:
    """Restrict joined warehouse queries to the assigned work location."""
    location_id = assigned_location_id(user)
    if location_id is None:
        return query
    return query.filter(Warehouse.location_id == location_id)


def enforce_warehouse_access(user: User, warehouse: Warehouse) -> None:
    """Reject warehouse access outside the assigned work location."""
    enforce_location_access(user, warehouse.location_id)
