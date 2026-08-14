# app/services/notification_service.py

from app.models.notification import Notification

class NotificationService:

    @staticmethod
    def create(
        db,
        user_id,
        title,
        message,
        reference_type=None,
        reference_id=None
    ):

        n = Notification(
            user_id=user_id,
            title=title,
            message=message,
            reference_type=reference_type,
            reference_id=reference_id
        )

        db.add(n)
        db.commit()
