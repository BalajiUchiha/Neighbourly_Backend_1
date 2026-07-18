import uuid
from datetime import datetime
from database import execute_query

class NotificationService:

    @staticmethod
    def create(db, user_id, type, title, body, reference_type=None, reference_id=None):
        query = """INSERT INTO notifications
                   (id, user_id, type, title, body, reference_type,
                    reference_id, is_read, created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,false,%s)"""
        params = (
            str(uuid.uuid4()), user_id, type,
            title, body, reference_type,
            str(reference_id) if reference_id else None,
            datetime.utcnow()
        )
        if hasattr(db, 'execute') and not hasattr(db, 'cursor'):
            # db is a cursor
            db.execute(query, params)
        else:
            # db is a connection
            execute_query(db, query, params)

    @staticmethod
    def get_all(db, current_user_id):
        notifications = execute_query(
            db,
            """SELECT id, user_id, type, title, body,
                      reference_type, reference_id,
                      is_read, created_at, read_at
               FROM notifications
               WHERE user_id = %s
               ORDER BY created_at DESC
               LIMIT 50""",
            (current_user_id,),
            fetch="all"
        )
        unread = execute_query(
            db,
            "SELECT COUNT(*) as count FROM notifications WHERE user_id = %s AND is_read = false",
            (current_user_id,),
            fetch="one"
        )
        return {
            "notifications": [
                {
                    **{k: str(v) if k == 'id' or k == 'reference_id' else v
                       for k, v in n.items()},
                    "created_at": n["created_at"].isoformat() if n["created_at"] else None,
                    "read_at": n["read_at"].isoformat() if n["read_at"] else None
                }
                for n in (notifications or [])
            ],
            "unread_count": unread["count"] if unread else 0,
            "total": len(notifications or [])
        }

    @staticmethod
    def get_unread_count(db, current_user_id):
        result = execute_query(
            db,
            "SELECT COUNT(*) as count FROM notifications WHERE user_id = %s AND is_read = false",
            (current_user_id,),
            fetch="one"
        )
        return {"count": result["count"] if result else 0}

    @staticmethod
    def mark_read(db, notification_id, current_user_id):
        from fastapi import HTTPException
        existing = execute_query(
            db,
            "SELECT id FROM notifications WHERE id = %s AND user_id = %s",
            (notification_id, current_user_id),
            fetch="one"
        )
        if not existing:
            raise HTTPException(404, "Notification not found")
        execute_query(
            db,
            "UPDATE notifications SET is_read = true, read_at = %s WHERE id = %s",
            (datetime.utcnow(), notification_id)
        )
        return {"message": "Marked as read"}

    @staticmethod
    def mark_all_read(db, current_user_id):
        execute_query(
            db,
            "UPDATE notifications SET is_read = true, read_at = %s WHERE user_id = %s AND is_read = false",
            (datetime.utcnow(), current_user_id)
        )
        return {"message": "All marked as read"}

    @staticmethod
    def delete(db, notification_id, current_user_id):
        from fastapi import HTTPException
        existing = execute_query(
            db,
            "SELECT id FROM notifications WHERE id = %s AND user_id = %s",
            (notification_id, current_user_id),
            fetch="one"
        )
        if not existing:
            raise HTTPException(404, "Notification not found")
        execute_query(
            db,
            "DELETE FROM notifications WHERE id = %s",
            (notification_id,)
        )
        return {"message": "Notification deleted"}
