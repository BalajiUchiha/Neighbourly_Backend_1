import uuid
from datetime import datetime, date
from fastapi import HTTPException
from database import execute_query
from utils.location import reverse_geocode

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

class ProfileService:
    @staticmethod
    async def get_profile_me(current_user_id: str, db):
        # Query 1 — user
        user = execute_query(
            db,
            """SELECT u.*,
                      uv.aadhaar_verified,
                      uac.free_daily_credits_remaining,
                      uac.free_monthly_credits_remaining,
                      uac.purchased_credits_remaining
               FROM users u
               LEFT JOIN user_verifications uv ON uv.user_id = u.id
               LEFT JOIN user_avatar_credits uac ON uac.user_id = u.id
               WHERE u.id = %s""",
            (current_user_id,),
            fetch="one"
        )
        if not user:
            raise HTTPException(404, "User not found")
            
        daily = user.get("free_daily_credits_remaining") or 0
        monthly = user.get("free_monthly_credits_remaining") or 0
        purchased = user.get("purchased_credits_remaining") or 0
        total_credits = daily + monthly + purchased
        
        user_dict = _serialize_row(user)
        user_dict["total_credits"] = total_credits
        user_dict["aadhaar_verified"] = bool(user.get("aadhaar_verified"))
        
        # Clean up database columns not expected in user profile payload
        for credit_col in ["free_daily_credits_remaining", "free_monthly_credits_remaining", "purchased_credits_remaining"]:
            user_dict.pop(credit_col, None)
            
        # Query 2 — worker profile
        worker_profile = None
        if user.get("is_worker"):
            wp = execute_query(
                db,
                "SELECT * FROM worker_profiles WHERE user_id = %s",
                (current_user_id,),
                fetch="one"
            )
            if wp:
                worker_profile = _serialize_row(wp)
                
        # Query 3 — stats
        jobs_completed_row = execute_query(
            db,
            """SELECT COUNT(*) as jobs_completed
               FROM applications a
               JOIN posts p ON p.id = a.post_id
               WHERE a.worker_id = %s AND p.status = 'completed'""",
            (current_user_id,),
            fetch="one"
        )
        jobs_completed = jobs_completed_row["jobs_completed"] if jobs_completed_row else 0
        
        posts_created_row = execute_query(
            db,
            "SELECT COUNT(*) as posts_created FROM posts WHERE poster_id = %s",
            (current_user_id,),
            fetch="one"
        )
        posts_created = posts_created_row["posts_created"] if posts_created_row else 0
        
        avg_rating_row = execute_query(
            db,
            """SELECT ROUND(AVG(stars)::numeric, 1) as avg_rating
               FROM ratings
               WHERE rated_id = %s AND is_revealed = true""",
            (current_user_id,),
            fetch="one"
        )
        avg_rating = float(avg_rating_row["avg_rating"]) if avg_rating_row and avg_rating_row["avg_rating"] is not None else None
        
        stats = {
            "jobs_completed": jobs_completed,
            "posts_created": posts_created,
            "avg_rating": avg_rating
        }
        
        return {
            "user": user_dict,
            "worker_profile": worker_profile,
            "stats": stats
        }

    @staticmethod
    async def get_my_posts(current_user_id: str, db):
        posts = execute_query(
            db,
            """SELECT p.*,
                      (SELECT COUNT(*) FROM applications a
                       WHERE a.post_id = p.id AND a.status != 'withdrawn') as applications_count
               FROM posts p
               WHERE p.poster_id = %s
               ORDER BY p.created_at DESC
               LIMIT 30""",
            (current_user_id,),
            fetch="all"
        ) or []
        
        return {"posts": [_serialize_row(p) for p in posts]}

    @staticmethod
    async def update_profile(current_user_id: str, body: dict, db):
        allowed = ['name', 'photo_url', 'preferred_language', 'phone', 'email']
        updates = {k: v for k, v in body.items() if k in allowed and v is not None}
        
        if not updates:
            return {"message": "Nothing to update"}
            
        set_clause = ", ".join([f"{k} = %s" for k in updates.keys()])
        values = list(updates.values()) + [datetime.utcnow(), current_user_id]
        
        execute_query(
            db,
            f"UPDATE users SET {set_clause}, updated_at = %s WHERE id = %s",
            values
        )
        
        return {"message": "Profile updated"}

    @staticmethod
    async def update_worker(current_user_id: str, body: dict, db):
        import json
        skills = body.get("skills", [])
        experience_levels = json.dumps(body.get("experience_levels", {}))
        availability_days = body.get("availability_days", [])
        availability_slots = body.get("availability_slots", [])
        wage_min = body.get("wage_min", 0)
        wage_max = body.get("wage_max", 0)
        open_to_no_exp_jobs = body.get("open_to_no_exp_jobs", True)
        feed_preferences = body.get("feed_preferences", [])
        willing_to_travel = body.get("willing_to_travel", False)
        
        existing = execute_query(
            db,
            "SELECT id FROM worker_profiles WHERE user_id = %s",
            (current_user_id,),
            fetch="one"
        )
        
        now = datetime.utcnow()
        
        if existing:
            # UPDATE
            execute_query(
                db,
                """UPDATE worker_profiles
                   SET skills = %s, experience_levels = %s, availability_days = %s, availability_slots = %s,
                       wage_min = %s, wage_max = %s, open_to_no_exp_jobs = %s, feed_preferences = %s,
                       willing_to_travel = %s, is_profile_complete = true, updated_at = %s
                   WHERE user_id = %s""",
                (skills, experience_levels, availability_days, availability_slots,
                 wage_min, wage_max, open_to_no_exp_jobs, feed_preferences, willing_to_travel, now, current_user_id)
            )
        else:
            # INSERT
            wp_id = str(uuid.uuid4())
            execute_query(
                db,
                """INSERT INTO worker_profiles
                   (id, user_id, skills, experience_levels, availability_days, availability_slots,
                    wage_min, wage_max, open_to_no_exp_jobs, feed_preferences, willing_to_travel, is_profile_complete, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, true, %s)""",
                (wp_id, current_user_id, skills, experience_levels, availability_days, availability_slots,
                 wage_min, wage_max, open_to_no_exp_jobs, feed_preferences, willing_to_travel, now)
            )
            # Update user is_worker field
            execute_query(
                db,
                "UPDATE users SET is_worker = true, updated_at = %s WHERE id = %s",
                (now, current_user_id)
            )
            
        # Update or insert RAG index row
        rag_existing = execute_query(
            db,
            "SELECT id FROM worker_rag_index WHERE worker_id = %s",
            (current_user_id,),
            fetch="one"
        )
        if rag_existing:
            execute_query(
                db,
                "UPDATE worker_rag_index SET is_dirty = true, updated_at = %s WHERE worker_id = %s",
                (now, current_user_id)
            )
        else:
            execute_query(
                db,
                """INSERT INTO worker_rag_index (id, worker_id, is_dirty, index_version, updated_at)
                   VALUES (%s, %s, true, 0, %s)""",
                (str(uuid.uuid4()), current_user_id, now)
            )
            
        return {"message": "Worker profile updated"}

    @staticmethod
    async def update_location(current_user_id: str, body: dict, db):
        latitude = body.get("latitude")
        longitude = body.get("longitude")
        
        if latitude is None or longitude is None:
            raise HTTPException(400, "latitude and longitude are required")
            
        loc_data = await reverse_geocode(latitude, longitude)
        
        area_name = loc_data.get("area_name", "")
        city = loc_data.get("city", "")
        state = loc_data.get("state", "")
        district = loc_data.get("district", "")
        
        now = datetime.utcnow()
        
        execute_query(
            db,
            """UPDATE users
               SET latitude = %s, longitude = %s,
                   area_name = %s, city = %s, state = %s,
                   district = %s, location_accuracy = 'exact',
                   updated_at = %s
               WHERE id = %s""",
            (latitude, longitude, area_name, city, state, district, now, current_user_id)
        )
        
        return {
            "area_name": area_name,
            "city": city,
            "district": district
        }
