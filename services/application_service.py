from database import execute_query
from fastapi import HTTPException
from datetime import datetime
from services.feed_service import FeedService
from services.notification_service import NotificationService
import uuid


class ApplicationService:

    @staticmethod
    async def get_applicants(post_id: str, current_user_id: str, db):
        # Verify requester is the poster
        post = execute_query(
            db,
            "SELECT id, poster_id, title, slots_remaining, workers_needed, latitude, longitude FROM posts WHERE id = %s",
            (post_id,),
            fetch="one"
        )
        if not post:
            raise HTTPException(404, "Post not found")
        if str(post["poster_id"]) != current_user_id:
            raise HTTPException(403, "Not authorised")

        applicants_raw = execute_query(
            db,
            """
            SELECT
                a.id, a.worker_id, a.status, a.note, a.counter_wage, a.applied_at,
                u.name, u.photo_url, u.trust_score, u.trust_badge,
                u.latitude as worker_lat, u.longitude as worker_lng,
                wp.skills
            FROM applications a
            JOIN users u ON u.id = a.worker_id
            LEFT JOIN worker_profiles wp ON wp.user_id = a.worker_id
            WHERE a.post_id = %s
            ORDER BY a.applied_at DESC
            """,
            (post_id,),
            fetch="all"
        )

        applicants = []
        for a in (applicants_raw or []):
            # Average rating
            rating_row = execute_query(
                db,
                """SELECT ROUND(AVG(stars)::numeric, 1) as avg
                   FROM ratings
                   WHERE rated_id = %s AND rating_type = 'client_to_worker' AND is_revealed = true""",
                (str(a["worker_id"]),),
                fetch="one"
            )

            # Total jobs (count of selected applications)
            jobs_row = execute_query(
                db,
                "SELECT COUNT(*) as count FROM applications WHERE worker_id = %s AND status = 'selected'",
                (str(a["worker_id"]),),
                fetch="one"
            )

            # Distance
            distance_km = None
            if (post.get("latitude") and post.get("longitude")
                    and a.get("worker_lat") and a.get("worker_lng")):
                distance_km = FeedService.calculate_distance_km(
                    post["latitude"], post["longitude"],
                    a["worker_lat"], a["worker_lng"]
                )

            applicants.append({
                "id": str(a["id"]),
                "worker_id": str(a["worker_id"]),
                "status": a["status"],
                "note": a["note"],
                "counter_wage": a["counter_wage"],
                "applied_at": a["applied_at"].isoformat() if a["applied_at"] else None,
                "name": a["name"],
                "photo_url": a["photo_url"],
                "trust_score": a["trust_score"],
                "trust_badge": a["trust_badge"],
                "skills": a["skills"] or [],
                "avg_rating": float(rating_row["avg"]) if rating_row and rating_row["avg"] else None,
                "total_jobs": jobs_row["count"] if jobs_row else 0,
                "distance_km": distance_km,
            })

        return {
            "post": {
                "title": post["title"],
                "slots_remaining": post["slots_remaining"],
                "workers_needed": post["workers_needed"],
            },
            "applicants": applicants
        }

    @staticmethod
    async def apply(body: dict, current_user_id: str, db):
        post_id = body.get("post_id")
        note = body.get("note")
        counter_wage = body.get("counter_wage")

        if not post_id:
            raise HTTPException(400, "post_id is required")

        post = execute_query(
            db,
            "SELECT id, poster_id, status, title FROM posts WHERE id = %s",
            (post_id,),
            fetch="one"
        )
        if not post:
            raise HTTPException(404, "Post not found")
        if post["status"] != "open":
            raise HTTPException(400, "Post is no longer open")
        if str(post["poster_id"]) == current_user_id:
            raise HTTPException(400, "Cannot apply to your own post")

        existing = execute_query(
            db,
            "SELECT id FROM applications WHERE post_id = %s AND worker_id = %s",
            (post_id, current_user_id),
            fetch="one"
        )
        if existing:
            raise HTTPException(409, "Already applied")

        application_id = str(uuid.uuid4())
        now = datetime.utcnow()

        execute_query(
            db,
            """INSERT INTO applications
               (id, post_id, worker_id, status, note, counter_wage, source, applied_at, status_updated_at)
               VALUES (%s,%s,%s,'applied',%s,%s,'organic',%s,%s)""",
            (application_id, post_id, current_user_id, note, counter_wage, now, now)
        )

        # Get applicant name
        applicant = execute_query(db, "SELECT name FROM users WHERE id = %s", (current_user_id,), fetch="one")
        applicant_name = applicant["name"] if applicant else "Someone"

        # Notify poster
        NotificationService.create(
            db, str(post["poster_id"]),
            "new_applicant",
            "New applicant",
            f"{applicant_name} applied to your post — {post['title']}",
            "application", application_id
        )

        return {"application_id": application_id, "message": "Applied successfully"}

    @staticmethod
    async def select_applicant(application_id: str, current_user_id: str, db):
        application = execute_query(
            db,
            "SELECT id, post_id, worker_id, status FROM applications WHERE id = %s",
            (application_id,),
            fetch="one"
        )
        if not application:
            raise HTTPException(404, "Application not found")

        post = execute_query(
            db,
            "SELECT id, poster_id, slots_remaining, title FROM posts WHERE id = %s",
            (str(application["post_id"]),),
            fetch="one"
        )
        if not post:
            raise HTTPException(404, "Post not found")
        if str(post["poster_id"]) != current_user_id:
            raise HTTPException(403, "Not authorised")
        if post["slots_remaining"] <= 0:
            raise HTTPException(400, "All positions filled")

        now = datetime.utcnow()
        worker_id = str(application["worker_id"])
        post_id = str(application["post_id"])
        new_slots = post["slots_remaining"] - 1

        # Update application status
        execute_query(
            db,
            "UPDATE applications SET status = 'selected', status_updated_at = %s WHERE id = %s",
            (now, application_id)
        )

        # Decrement slots; mark filled if hits 0
        if new_slots == 0:
            execute_query(
                db,
                "UPDATE posts SET slots_remaining = 0, status = 'filled', updated_at = %s WHERE id = %s",
                (now, post_id)
            )
        else:
            execute_query(
                db,
                "UPDATE posts SET slots_remaining = %s, updated_at = %s WHERE id = %s",
                (new_slots, now, post_id)
            )

        # job_lifecycle_events
        execute_query(
            db,
            """INSERT INTO job_lifecycle_events (id, post_id, application_id, event_type, triggered_by, created_at)
               VALUES (%s,%s,%s,'worker_selected',%s,%s)""",
            (str(uuid.uuid4()), post_id, application_id, current_user_id, now)
        )

        # Create chat row
        chat_id = str(uuid.uuid4())
        execute_query(
            db,
            """INSERT INTO chats (id, application_id, post_id, poster_id, worker_id, bargain_status, created_at)
               VALUES (%s,%s,%s,%s,%s,'not_started',%s)""",
            (chat_id, application_id, post_id, current_user_id, worker_id, now)
        )

        # Notify selected worker
        NotificationService.create(
            db, worker_id,
            "application_selected",
            "You've been selected! 🎉",
            f"You were selected for — {post['title']}. Chat is now open.",
            "application", application_id
        )

        # Notify other pending applicants (status change not applied — just notify)
        other_applicants = execute_query(
            db,
            """SELECT id, worker_id FROM applications
               WHERE post_id = %s AND status = 'applied' AND id != %s""",
            (post_id, application_id),
            fetch="all"
        )
        for other in (other_applicants or []):
            NotificationService.create(
                db, str(other["worker_id"]),
                "application_rejected",
                "Not selected this time",
                f"You were not selected for — {post['title']}. Keep applying!",
                "application", str(other["id"])
            )

        return {"chat_id": chat_id, "message": "Worker selected and chat created"}

    @staticmethod
    async def reject_applicant(application_id: str, current_user_id: str, db):
        application = execute_query(
            db,
            "SELECT id, post_id, worker_id FROM applications WHERE id = %s",
            (application_id,),
            fetch="one"
        )
        if not application:
            raise HTTPException(404, "Application not found")

        post = execute_query(
            db,
            "SELECT id, poster_id, title FROM posts WHERE id = %s",
            (str(application["post_id"]),),
            fetch="one"
        )
        if not post:
            raise HTTPException(404, "Post not found")
        if str(post["poster_id"]) != current_user_id:
            raise HTTPException(403, "Not authorised")

        now = datetime.utcnow()
        worker_id = str(application["worker_id"])

        execute_query(
            db,
            "UPDATE applications SET status = 'rejected', status_updated_at = %s WHERE id = %s",
            (now, application_id)
        )

        execute_query(
            db,
            """INSERT INTO job_lifecycle_events (id, post_id, application_id, event_type, triggered_by, created_at)
               VALUES (%s,%s,%s,'worker_rejected',%s,%s)""",
            (str(uuid.uuid4()), str(application["post_id"]), application_id, current_user_id, now)
        )

        NotificationService.create(
            db, worker_id,
            "application_rejected",
            "Not selected this time",
            f"You were not selected for — {post['title']}. Keep applying!",
            "application", application_id
        )

        return {"message": "Applicant passed"}
