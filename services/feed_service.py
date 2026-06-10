from database import execute_query
from math import cos, radians, sqrt
from datetime import datetime

class FeedService:

    @staticmethod
    def calculate_distance_km(lat1, lng1, lat2, lng2):
        dlat = (float(lat2) - float(lat1)) * 111.0
        dlng = (float(lng2) - float(lng1)) * 111.0 * abs(cos(radians(float(lat1))))
        return round(sqrt(dlat**2 + dlng**2), 1)

    @staticmethod
    def get_bounding_box(lat, lng, radius_km):
        delta_lat = radius_km / 111.0
        delta_lng = radius_km / (111.0 * abs(cos(radians(float(lat)))))
        return {
            "min_lat": float(lat) - delta_lat,
            "max_lat": float(lat) + delta_lat,
            "min_lng": float(lng) - delta_lng,
            "max_lng": float(lng) + delta_lng
        }

    @staticmethod
    async def get_feed(filter, radius_km, current_user_id, db):

        # Get current user
        user = execute_query(
            db,
            "SELECT * FROM users WHERE id = %s",
            (current_user_id,),
            fetch="one"
        )
        if not user:
            return {"posts": [], "total": 0}

        # Build base WHERE conditions
        base_conditions = """
            p.status = 'open'
            AND p.poster_id != %s
        """
        base_params = [current_user_id]

        # Location filter
        if user["latitude"] and user["longitude"]:
            box = FeedService.get_bounding_box(
                user["latitude"], user["longitude"], radius_km
            )
            base_conditions += """
                AND p.latitude BETWEEN %s AND %s
                AND p.longitude BETWEEN %s AND %s
            """
            base_params += [
                box["min_lat"], box["max_lat"],
                box["min_lng"], box["max_lng"]
            ]
        elif user["district"]:
            base_conditions += " AND p.district = %s"
            base_params.append(user["district"])

        # Filter specific conditions
        filter_conditions = ""
        filter_params = []
        order_by = "ORDER BY p.created_at DESC"

        if filter == "all":
            order_by = """ORDER BY 
                CASE p.urgency_tag 
                    WHEN 'today' THEN 1 
                    WHEN 'tomorrow' THEN 2 
                    WHEN 'this_week' THEN 3 
                    ELSE 4 
                END, p.created_at DESC"""

        elif filter == "for_me":
            worker = execute_query(
                db,
                "SELECT skills FROM worker_profiles WHERE user_id = %s",
                (current_user_id,),
                fetch="one"
            )
            if worker and worker["skills"]:
                filter_conditions = "AND p.task_type = ANY(%s)"
                filter_params.append(worker["skills"])
            else:
                if user["district"]:
                    filter_conditions = "AND p.district = %s"
                    filter_params.append(user["district"])

        elif filter == "part_time":
            filter_conditions = "AND p.job_nature = 'part_time'"
            order_by = "ORDER BY p.pay_per_person DESC NULLS LAST, p.created_at DESC"

        elif filter == "volunteer":
            filter_conditions = "AND p.post_category = 'volunteer'"
            order_by = "ORDER BY p.work_date ASC NULLS LAST, p.created_at DESC"

        elif filter == "no_exp":
            filter_conditions = "AND p.no_exp_needed = true"
            order_by = """ORDER BY 
                CASE p.urgency_tag 
                    WHEN 'today' THEN 1 
                    WHEN 'tomorrow' THEN 2 
                    ELSE 3 
                END, p.created_at DESC"""

        elif filter == "urgent":
            filter_conditions = "AND p.urgency_tag IN ('today', 'tomorrow')"
            order_by = """ORDER BY 
                CASE p.urgency_tag 
                    WHEN 'today' THEN 1 
                    ELSE 2 
                END, p.created_at DESC"""

        query = f"""
            SELECT p.*,
                u.name as poster_name,
                u.photo_url as poster_photo,
                u.trust_score as poster_trust_score
            FROM posts p
            JOIN users u ON u.id = p.poster_id
            WHERE {base_conditions} {filter_conditions}
            {order_by}
            LIMIT 20
        """

        posts = execute_query(
            db,
            query,
            base_params + filter_params,
            fetch="all"
        )

        return {
            "posts": FeedService.enrich_posts(posts, user, db),
            "total": len(posts),
            "radius_km": radius_km,
            "filter": filter
        }

    @staticmethod
    def enrich_posts(posts, user, db):
        enriched = []
        for post in posts:
            # Get images
            images = execute_query(
                db,
                "SELECT image_url, display_order FROM post_images WHERE post_id = %s ORDER BY display_order",
                (str(post["id"]),),
                fetch="all"
            )

            # Get application count
            app_count = execute_query(
                db,
                "SELECT COUNT(*) as count FROM applications WHERE post_id = %s AND status != 'withdrawn'",
                (str(post["id"]),),
                fetch="one"
            )

            # Get poster ratings
            worker_rating = execute_query(
                db,
                """SELECT ROUND(AVG(stars)::numeric, 1) as avg 
                   FROM ratings 
                   WHERE rated_id = %s AND rating_type = 'client_to_worker' AND is_revealed = true""",
                (str(post["poster_id"]),),
                fetch="one"
            )
            poster_rating = execute_query(
                db,
                """SELECT ROUND(AVG(stars)::numeric, 1) as avg 
                   FROM ratings 
                   WHERE rated_id = %s AND rating_type = 'worker_to_client' AND is_revealed = true""",
                (str(post["poster_id"]),),
                fetch="one"
            )

            # Distance
            distance_km = None
            if (user.get("latitude") and user.get("longitude")
                    and post.get("latitude") and post.get("longitude")):
                distance_km = FeedService.calculate_distance_km(
                    user["latitude"], user["longitude"],
                    post["latitude"], post["longitude"]
                )

            enriched.append({
                "id": str(post["id"]),
                "poster_id": str(post["poster_id"]),
                "poster": {
                    "id": str(post["poster_id"]),
                    "name": post["poster_name"],
                    "photo_url": post["poster_photo"],
                    "worker_rating": float(worker_rating["avg"]) if worker_rating and worker_rating["avg"] else None,
                    "poster_rating": float(poster_rating["avg"]) if poster_rating and poster_rating["avg"] else None
                },
                "title": post["title"],
                "description": post["description"],
                "task_type": post["task_type"],
                "post_category": post["post_category"],
                "job_nature": post["job_nature"],
                "workers_needed": post["workers_needed"],
                "slots_remaining": post["slots_remaining"],
                "pay_per_person": post["pay_per_person"],
                "no_exp_needed": post["no_exp_needed"],
                "urgency_tag": post["urgency_tag"],
                "status": post["status"],
                "area_name": post["area_name"],
                "district": post["district"],
                "distance_km": distance_km,
                "work_date": post["work_date"].isoformat() if post["work_date"] else None,
                "work_time_slot": post["work_time_slot"],
                "tags": post["tags"] or [],
                "raw_input_text": post["raw_input_text"],
                "has_voice_input": post["raw_input_text"] is None and post["ai_generated"],
                "images": images or [],
                "applications_count": app_count["count"] if app_count else 0,
                "suggested_workers": None,
                "created_at": post["created_at"].isoformat() if post["created_at"] else None,
                "is_own_post": False
            })
        return enriched

    @staticmethod
    async def get_active_post(current_user_id, db):
        user = execute_query(
            db,
            "SELECT * FROM users WHERE id = %s",
            (current_user_id,),
            fetch="one"
        )

        post = execute_query(
            db,
            """SELECT p.* FROM posts p 
               WHERE p.poster_id = %s AND p.status = 'open'
               ORDER BY p.created_at DESC LIMIT 1""",
            (current_user_id,),
            fetch="one"
        )

        if not post:
            return {"post": None}

        images = execute_query(
            db,
            "SELECT image_url, display_order FROM post_images WHERE post_id = %s ORDER BY display_order",
            (str(post["id"]),),
            fetch="all"
        )

        app_count = execute_query(
            db,
            "SELECT COUNT(*) as count FROM applications WHERE post_id = %s AND status != 'withdrawn'",
            (str(post["id"]),),
            fetch="one"
        )

        # Get suggested workers
        suggested = FeedService.get_suggested_workers(post, user, db)

        return {
            "post": {
                "id": str(post["id"]),
                "poster_id": str(post["poster_id"]),
                "poster": {
                    "id": str(user["id"]),
                    "name": user["name"],
                    "photo_url": user["photo_url"],
                    "worker_rating": None,
                    "poster_rating": None
                },
                "title": post["title"],
                "description": post["description"],
                "task_type": post["task_type"],
                "post_category": post["post_category"],
                "job_nature": post["job_nature"],
                "workers_needed": post["workers_needed"],
                "slots_remaining": post["slots_remaining"],
                "pay_per_person": post["pay_per_person"],
                "no_exp_needed": post["no_exp_needed"],
                "urgency_tag": post["urgency_tag"],
                "status": post["status"],
                "area_name": post["area_name"],
                "district": post["district"],
                "distance_km": 0,
                "work_date": post["work_date"].isoformat() if post["work_date"] else None,
                "work_time_slot": post["work_time_slot"],
                "tags": post["tags"] or [],
                "raw_input_text": post["raw_input_text"],
                "has_voice_input": post["raw_input_text"] is None and post["ai_generated"],
                "images": images or [],
                "applications_count": app_count["count"] if app_count else 0,
                "suggested_workers": suggested,
                "created_at": post["created_at"].isoformat() if post["created_at"] else None,
                "is_own_post": True
            }
        }

    @staticmethod
    def get_suggested_workers(post, current_user, db):
        # For jobs with experience needed — match by task_type
        # For no_exp_needed — show anyone nearby in same district
        if post["no_exp_needed"]:
            workers = execute_query(
                db,
                """SELECT u.id, u.name, u.photo_url, u.trust_score,
                          u.latitude, u.longitude
                   FROM users u
                   WHERE u.is_worker = true
                   AND u.is_active = true
                   AND u.district = %s
                   AND u.id != %s
                   ORDER BY u.trust_score DESC
                   LIMIT 5""",
                (post["district"], str(current_user["id"])),
                fetch="all"
            )
        else:
            workers = execute_query(
                db,
                """SELECT u.id, u.name, u.photo_url, u.trust_score,
                          u.latitude, u.longitude
                   FROM users u
                   JOIN worker_profiles wp ON wp.user_id = u.id
                   WHERE u.is_worker = true
                   AND u.is_active = true
                   AND u.district = %s
                   AND u.id != %s
                   AND %s = ANY(wp.skills)
                   ORDER BY u.trust_score DESC
                   LIMIT 5""",
                (post["district"], str(current_user["id"]), post["task_type"]),
                fetch="all"
            )

        result = []
        for w in (workers or []):
            distance_km = 0.0
            if (post.get("latitude") and post.get("longitude")
                    and w.get("latitude") and w.get("longitude")):
                distance_km = FeedService.calculate_distance_km(
                    post["latitude"], post["longitude"],
                    w["latitude"], w["longitude"]
                )
            result.append({
                "id": str(w["id"]),
                "name": w["name"],
                "photo_url": w["photo_url"],
                "trust_score": w["trust_score"],
                "trust_score_display": str(w["trust_score"]),
                "distance_km": distance_km
            })
        return result

    @staticmethod
    async def update_location(body, current_user_id, db):
        execute_query(
            db,
            "UPDATE users SET latitude = %s, longitude = %s, updated_at = %s WHERE id = %s",
            (body.get("latitude"), body.get("longitude"), datetime.utcnow(), current_user_id)
        )
        return {"status": "location updated"}
