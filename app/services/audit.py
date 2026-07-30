from app.services.activity_service import ActivityService


def record_audit(db, user, action: str, entity_type: str, summary: str, **kwargs):
    return ActivityService.log(
        db=db,
        user=user,
        action=action,
        entity_type=entity_type,
        summary=summary,
        **kwargs,
    )
