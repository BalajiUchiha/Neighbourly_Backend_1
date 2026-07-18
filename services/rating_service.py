import uuid
from datetime import datetime, date
from fastapi import HTTPException
from database import execute_query
from services.trust_service import TrustService
from services.notification_service import NotificationService

def _serialize_row(row):
    if not row:
        return row
    res = {}
    for k, v in row.items():
        if isinstance(v, uuid.UUID):
            res[k] = str(v)
        elif isinstance(v, (datetime, date)):
            res[k] = v.isoformat()
        else:
            res[k] = v
    return res

class RatingService:
    @staticmethod
    async def get_rating_context(chat_id: str, current_user_id: str, db):
        chat = execute_query(db, "SELECT * FROM chats WHERE id = %s", (chat_id,), fetch="one")
        if not chat:
            raise HTTPException(404, "Chat not found")
            
        poster_id = str(chat["poster_id"])
        worker_id = str(chat["worker_id"])
        application_id = str(chat["application_id"])
        
        if current_user_id not in (poster_id, worker_id):
            raise HTTPException(403, "Not authorized to access this rating context")
            
        is_rating_worker = (current_user_id == poster_id)
        rated_user_id = worker_id if is_rating_worker else poster_id
        
        # Check if already submitted
        existing = execute_query(
            db,
            "SELECT id FROM ratings WHERE application_id = %s AND rater_id = %s",
            (application_id, current_user_id),
            fetch="one"
        )
        if existing:
            return {"already_submitted": True}
            
        post = execute_query(db, "SELECT title, work_date FROM posts WHERE id = %s", (str(chat["post_id"]),), fetch="one")
        rated_user = execute_query(db, "SELECT id, name, photo_url FROM users WHERE id = %s", (rated_user_id,), fetch="one")
        
        return {
            "chat": _serialize_row(chat),
            "post": _serialize_row(post),
            "rated_user": _serialize_row(rated_user),
            "is_rating_worker": is_rating_worker,
            "already_submitted": False
        }

    @staticmethod
    async def submit_rating(current_user_id: str, body: dict, db):
        chat_id = body.get("chat_id")
        stars = body.get("stars")
        review_text = body.get("review_text", "")
        tags = body.get("tags", [])
        
        if not chat_id:
            raise HTTPException(400, "chat_id is required")
        if stars is None or stars < 1 or stars > 5:
            raise HTTPException(400, "Stars must be between 1 and 5")
            
        chat = execute_query(db, "SELECT * FROM chats WHERE id = %s", (chat_id,), fetch="one")
        if not chat:
            raise HTTPException(404, "Chat not found")
            
        poster_id = str(chat["poster_id"])
        worker_id = str(chat["worker_id"])
        application_id = str(chat["application_id"])
        post_id = str(chat["post_id"])
        
        if current_user_id not in (poster_id, worker_id):
            raise HTTPException(403, "Not authorized")
            
        # Determine roles
        if current_user_id == poster_id:
            rater_id = poster_id
            rated_id = worker_id
            role_of_rater = "job_creator"
            rating_type = "client_to_worker"
        else:
            rater_id = worker_id
            rated_id = poster_id
            role_of_rater = "job_doer"
            rating_type = "worker_to_client"
            
        # Check duplicate
        existing = execute_query(
            db,
            "SELECT id FROM ratings WHERE application_id = %s AND rater_id = %s",
            (application_id, rater_id),
            fetch="one"
        )
        if existing:
            raise HTTPException(409, "Already submitted")
            
        full_review = review_text
        if tags:
            full_review = review_text + " | Tags: " + ", ".join(tags)
            
        rating_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        # Insert rating
        execute_query(
            db,
            """INSERT INTO ratings
               (id, application_id, post_id, rater_id, rated_id, role_of_rater, rating_type, stars, review_text, is_submitted, is_revealed, submitted_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, true, false, %s)""",
            (rating_id, application_id, post_id, rater_id, rated_id, role_of_rater, rating_type, stars, full_review, now)
        )
        
        # Check if both sides submitted
        ratings = execute_query(
            db,
            "SELECT * FROM ratings WHERE application_id = %s AND is_submitted = true",
            (application_id,),
            fetch="all"
        ) or []
        
        if len(ratings) == 2:
            # Get user names for notification bodies
            poster_user = execute_query(db, "SELECT name FROM users WHERE id = %s", (poster_id,), fetch="one")
            worker_user = execute_query(db, "SELECT name FROM users WHERE id = %s", (worker_id,), fetch="one")
            poster_name = poster_user["name"] if poster_user else "Poster"
            worker_name = worker_user["name"] if worker_user else "Worker"

            r_poster = next((r for r in ratings if str(r["rater_id"]) == poster_id), None)
            r_worker = next((r for r in ratings if str(r["rater_id"]) == worker_id), None)
            
            poster_stars = r_poster["stars"] if r_poster else 0
            worker_stars = r_worker["stars"] if r_worker else 0

            # Mutual reveal
            with db.cursor() as cur:
                # Update reveal flags
                cur.execute(
                    "UPDATE ratings SET is_revealed = true, revealed_at = %s WHERE application_id = %s",
                    (now, application_id)
                )
                
                # Apply trust score progressions to both users using transaction cursor
                for r in ratings:
                    # Apply to rated_id (the person who received this rating)
                    TrustService.apply_rating_score(cur, str(r["rated_id"]), r["stars"], application_id)
                    
                # Insert notifications
                NotificationService.create(
                    cur, poster_id, "review_revealed", "Your review is now visible 👁️",
                    f"{worker_name} left you a {worker_stars} star review", "application", application_id
                )
                NotificationService.create(
                    cur, worker_id, "review_revealed", "Your review is now visible 👁️",
                    f"{poster_name} left you a {poster_stars} star review", "application", application_id
                )
                
            db.commit()
            
            # Find the rating written *by the other user* about *current_user*
            their_rating_row = next((r for r in ratings if str(r["rater_id"]) != current_user_id), None)
            their_rating = their_rating_row["stars"] if their_rating_row else 0
            their_review = their_rating_row["review_text"] if their_rating_row else ""
            
            return {
                "both_revealed": True,
                "their_rating": their_rating,
                "their_review": their_review
            }
        else:
            return {"both_revealed": False}

    @staticmethod
    async def get_trust_score(current_user_id: str, db):
        # Query 1: user trust info
        user = execute_query(db, "SELECT trust_score, trust_badge FROM users WHERE id = %s", (current_user_id,), fetch="one")
        if not user:
            raise HTTPException(404, "User not found")
            
        trust_score = user.get("trust_score") or 0
        trust_badge = user.get("trust_badge") or "new"
        
        # Query 2: stats
        jobs_completed_row = execute_query(
            db,
            """SELECT COUNT(*) as count FROM applications a
               JOIN posts p ON p.id = a.post_id
               WHERE a.worker_id = %s AND p.status = 'completed'""",
            (current_user_id,),
            fetch="one"
        )
        jobs_completed = jobs_completed_row["count"] if jobs_completed_row else 0
        
        avg_rating_row = execute_query(
            db,
            """SELECT ROUND(AVG(stars)::numeric, 1) as avg
               FROM ratings
               WHERE rated_id = %s AND is_revealed = true""",
            (current_user_id,),
            fetch="one"
        )
        avg_rating = float(avg_rating_row["avg"]) if avg_rating_row and avg_rating_row["avg"] is not None else None
        
        cancellations_row = execute_query(
            db,
            "SELECT COUNT(*) as count FROM cancellations WHERE cancelled_by = %s",
            (current_user_id,),
            fetch="one"
        )
        cancellations = cancellations_row["count"] if cancellations_row else 0
        
        stats = {
            "jobs_completed": jobs_completed,
            "avg_rating": avg_rating,
            "cancellations": cancellations,
            "on_time_rate": 100
        }
        
        # Query 3: score history
        history_raw = execute_query(
            db,
            """SELECT event_type, score_change, score_before, score_after, reason, created_at
               FROM trust_score_logs
               WHERE user_id = %s
               ORDER BY created_at DESC
               LIMIT 20""",
            (current_user_id,),
            fetch="all"
        ) or []
        history = [_serialize_row(h) for h in history_raw]
        
        return {
            "trust_score": trust_score,
            "trust_badge": trust_badge,
            "stats": stats,
            "history": history
        }

    @staticmethod
    async def get_my_reviews(current_user_id: str, db):
        reviews_raw = execute_query(
            db,
            """SELECT r.stars, r.review_text, r.rating_type, r.revealed_at,
                      p.title as post_title,
                      u.name as reviewer_name, u.photo_url as reviewer_photo
               FROM ratings r
               JOIN posts p ON p.id = r.post_id
               JOIN users u ON u.id = r.rater_id
               WHERE r.rated_id = %s AND r.is_revealed = true
               ORDER BY r.revealed_at DESC""",
            (current_user_id,),
            fetch="all"
        ) or []
        reviews = [_serialize_row(r) for r in reviews_raw]
        return {"reviews": reviews}
