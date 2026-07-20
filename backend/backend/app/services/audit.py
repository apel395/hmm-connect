from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def record_audit(
    db: Session,
    user,
    action: str,
    entity_type: str,
    entity_id: int | None,
    summary: str,
    details: dict | None = None,
) -> AuditLog:
    """Create an immutable audit event with an identity snapshot.

    The snapshot is intentional. A user can change department, location, or
    roles later, but historical audit events must keep the context that was
    true when the event happened.
    """
    department = getattr(user, "department", None)
    location = getattr(user, "location", None)
    roles = getattr(user, "roles", []) or []

    audit_log = AuditLog(
        user_id=getattr(user, "id", None),
        actor_name=getattr(user, "full_name", None),
        department_id=getattr(user, "department_id", None),
        department_name=getattr(department, "name", None),
        location_id=getattr(user, "location_id", None),
        location_name=getattr(location, "name", None),
        role_names=[role.name for role in roles],
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        details=details,
    )

    db.add(audit_log)

    return audit_log
