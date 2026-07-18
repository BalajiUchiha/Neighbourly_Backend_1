import uuid
from datetime import datetime

def _db_exec(db_or_cur, query, params=None):
    if hasattr(db_or_cur, 'execute') and not hasattr(db_or_cur, 'cursor'):
        db_or_cur.execute(query, params or ())
    else:
        with db_or_cur.cursor() as cur:
            cur.execute(query, params or ())
        db_or_cur.commit()

def _db_fetch_one(db_or_cur, query, params=None):
    if hasattr(db_or_cur, 'execute') and not hasattr(db_or_cur, 'cursor'):
        db_or_cur.execute(query, params or ())
        row = db_or_cur.fetchone()
        if row and db_or_cur.description:
            cols = [d[0] for d in db_or_cur.description]
            return dict(zip(cols, row))
        return None
    else:
        from database import execute_query
        return execute_query(db_or_cur, query, params, fetch="one")

class TrustService:

    SCORE_MAP = {
        5: +5,
        4: +3,
        3: 0,
        2: -5,
        1: -5
    }

    @staticmethod
    def apply_rating_score(db, user_id, stars, application_id):
        score_change = TrustService.SCORE_MAP.get(stars, 0)
        if score_change == 0:
            return

        # Get current score
        user = _db_fetch_one(
            db,
            "SELECT trust_score, trust_badge FROM users WHERE id = %s",
            (user_id,)
        )
        if not user:
            return
            
        current_score = user.get("trust_score") or 0
        new_score = max(0, min(100, current_score + score_change))

        # Determine new badge
        new_badge = TrustService.get_badge(new_score)

        # Update user
        _db_exec(
            db,
            "UPDATE users SET trust_score = %s, trust_badge = %s, updated_at = %s WHERE id = %s",
            (new_score, new_badge, datetime.utcnow(), user_id)
        )

        # Log it
        _db_exec(
            db,
            """INSERT INTO trust_score_logs
               (id, user_id, event_type, score_change, score_before, score_after,
                rating_weight, reference_type, reference_id, reason, created_at)
               VALUES (%s,%s,'rating_received',%s,%s,%s,1.0,'application',%s,%s,%s)""",
            (
                str(uuid.uuid4()), user_id, score_change,
                current_score, new_score, application_id,
                f"Received {stars} star rating",
                datetime.utcnow()
            )
        )

        # Mark worker_rag_index dirty so RAG re-indexes
        _db_exec(
            db,
            "UPDATE worker_rag_index SET is_dirty = true, updated_at = %s WHERE worker_id = %s",
            (datetime.utcnow(), user_id)
        )

        # Insert notification
        from services.notification_service import NotificationService
        change_str = f"+{score_change}" if score_change > 0 else f"{score_change}"
        NotificationService.create(
            db, user_id, "trust_score_changed", "Trust score updated 📊",
            f"Your score changed by {change_str} points. Now at {new_score}", "rating", application_id
        )

    @staticmethod
    def get_badge(score):
        if score >= 71: return 'elite'
        if score >= 41: return 'trusted'
        if score >= 21: return 'growing'
        return 'new'

    @staticmethod
    def apply_completion_score(db, user_id, application_id):
        # Called on job completion — +8 points
        user = _db_fetch_one(
            db,
            "SELECT trust_score, trust_badge FROM users WHERE id = %s",
            (user_id,)
        )
        if not user:
            return
            
        current = user.get("trust_score") or 0
        new_score = min(100, current + 8)
        new_badge = TrustService.get_badge(new_score)

        _db_exec(
            db,
            "UPDATE users SET trust_score = %s, trust_badge = %s, updated_at = %s WHERE id = %s",
            (new_score, new_badge, datetime.utcnow(), user_id)
        )
        
        _db_exec(
            db,
            """INSERT INTO trust_score_logs
               (id, user_id, event_type, score_change, score_before, score_after,
                rating_weight, reference_type, reference_id, reason, created_at)
               VALUES (%s,%s,'job_completed',8,%s,%s,1.0,'application',%s,%s,%s)""",
            (
                str(uuid.uuid4()), user_id, current, new_score,
                application_id, "Job completed successfully",
                datetime.utcnow()
            )
        )
        
        _db_exec(
            db,
            "UPDATE worker_rag_index SET is_dirty = true, updated_at = %s WHERE worker_id = %s",
            (datetime.utcnow(), user_id)
        )

        # Insert notification
        from services.notification_service import NotificationService
        NotificationService.create(
            db, user_id, "trust_score_changed", "Trust score updated 📊",
            f"Your score changed by +8 points. Now at {new_score}", "rating", application_id
        )
