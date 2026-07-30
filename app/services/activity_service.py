from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


class ActivityService:

    @staticmethod
    def log(
        db: Session,
        *,
        user,
        action: str,
        entity_type: str,
        summary: str,
        entity_id: int | None = None,
        document_type: str | None = None,
        document_number: str | None = None,
        document_status: str | None = None,
        reference_document: str | None = None,
        workflow_id: str | None = None,
        approval_level: int | None = None,
        approval_step: str | None = None,
        details: dict[str, Any] | None = None,
        before_data: dict[str, Any] | None = None,
        after_data: dict[str, Any] | None = None,
        ip_address: str | None = None,
        client_info: str | None = None,

    ) -> AuditLog:

        activity = AuditLog(

            # --------------------------
            # User
            # --------------------------

            user_id=user.id
            if user
            else None,


            # --------------------------
            # Actor Snapshot
            # --------------------------

            actor_name=getattr(
                user,
                "full_name",
                None,
            )
            if user
            else None,


            department_id=getattr(
                user,
                "department_id",
                None,
            )
            if user
            else None,


            department_name=user.department.name
            if user and getattr(user, "department", None)
            else None,


            location_id=getattr(
                user,
                "location_id",
                None,
            )
            if user
            else None,


            location_name=user.location.name
            if user and getattr(user, "location", None)
            else None,


            role_names=[
                role.name
                for role in getattr(user, "roles", [])
            ]
            if user
            else None,


            # --------------------------
            # Action
            # --------------------------

            action=action,

            entity_type=entity_type,

            entity_id=entity_id,

            summary=summary,


            # --------------------------
            # Document
            # --------------------------

            document_type=document_type,

            document_number=document_number,

            document_status=document_status,

            reference_document=reference_document,


            # --------------------------
            # Workflow
            # --------------------------

            workflow_id=workflow_id,

            approval_level=approval_level,

            approval_step=approval_step,


            # --------------------------
            # Data Snapshot
            # --------------------------

            before_data=before_data,

            after_data=after_data,

            details=details,


            # --------------------------
            # Request Information
            # --------------------------

            ip_address=ip_address,

            client_info=client_info,
        )


        db.add(activity)

        db.flush()

        return activity


# Backwards-compatible name used by recovered purchasing and payments modules.
AuditService = ActivityService
