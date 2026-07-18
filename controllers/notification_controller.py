from services.notification_service import NotificationService

class NotificationController:
    @staticmethod
    async def get_all(current_user_id: str, db):
        return NotificationService.get_all(db, current_user_id)

    @staticmethod
    async def get_unread_count(current_user_id: str, db):
        return NotificationService.get_unread_count(db, current_user_id)

    @staticmethod
    async def mark_read(notification_id: str, current_user_id: str, db):
        return NotificationService.mark_read(db, notification_id, current_user_id)

    @staticmethod
    async def mark_all_read(current_user_id: str, db):
        return NotificationService.mark_all_read(db, current_user_id)

    @staticmethod
    async def delete(notification_id: str, current_user_id: str, db):
        return NotificationService.delete(db, notification_id, current_user_id)
