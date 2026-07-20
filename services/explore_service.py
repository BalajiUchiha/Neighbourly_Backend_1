from database import execute_query
from services.feed_service import FeedService


class ExploreService:

    # ─── Public Dispatcher ────────────────────────────────────────────────────
    @staticmethod
    async def get_map(lat, lng, radius_km, district, filter_type, current_user_id, db):
        if lat is not None and lng is not None:
            return await ExploreService.get_map_gps(
                lat, lng, radius_km, filter_type, current_user_id, db
            )
        elif district:
            return await ExploreService.get_map_district(
                district, current_user_id, db
            )
        else:
            return {
                "posts":       [],
                "workers":     [],
                "connections": [],
                "mode":        "none",
                "radius_km":   None,
            }

    # ─── GPS Mode ─────────────────────────────────────────────────────────────
    @staticmethod
    async def get_map_gps(lat, lng, radius_km, filter_type, current_user_id, db):
        box = FeedService.get_bounding_box(lat, lng, radius_km)
        min_lat = box["min_lat"]
        max_lat = box["max_lat"]
        min_lng = box["min_lng"]
        max_lng = box["max_lng"]

        # ── Query 1: Posts within radius ──────────────────────────────────────
        posts_raw = execute_query(
            db,
            """
            SELECT p.*,
                   u.name  AS poster_name,
                   u.photo_url AS poster_photo,
                   u.trust_score AS poster_trust
            FROM posts p
            JOIN users u ON u.id = p.poster_id
            WHERE p.status = 'open'
              AND p.latitude  BETWEEN %s AND %s
              AND p.longitude BETWEEN %s AND %s
              AND p.poster_id != %s
            ORDER BY p.created_at DESC
            LIMIT 30
            """,
            (min_lat, max_lat, min_lng, max_lng, current_user_id),
            fetch="all"
        )

        posts = ExploreService._enrich_posts(posts_raw, lat, lng, db)

        # ── Query 2: Workers in area (only when filter = workers or all) ──────
        workers = []
        if filter_type in ("workers", "all"):
            workers_raw = execute_query(
                db,
                """
                SELECT u.id, u.name, u.photo_url, u.trust_score,
                       u.trust_badge, u.latitude, u.longitude,
                       wp.skills, wp.wage_min, wp.wage_max
                FROM users u
                JOIN worker_profiles wp ON wp.user_id = u.id
                WHERE u.is_worker  = true
                  AND u.is_active  = true
                  AND u.latitude   BETWEEN %s AND %s
                  AND u.longitude  BETWEEN %s AND %s
                  AND u.id != %s
                ORDER BY u.trust_score DESC
                LIMIT 20
                """,
                (min_lat, max_lat, min_lng, max_lng, current_user_id),
                fetch="all"
            )
            workers = ExploreService._enrich_workers(workers_raw, lat, lng)

        # ── Query 3: Connection lines (hired workers ↔ active posts) ──────────
        connections_raw = execute_query(
            db,
            """
            SELECT
                p.latitude  AS post_lat,
                p.longitude AS post_lng,
                u.latitude  AS worker_lat,
                u.longitude AS worker_lng,
                p.id        AS post_id,
                u.id        AS worker_id
            FROM applications a
            JOIN posts p ON p.id = a.post_id
            JOIN users u ON u.id = a.worker_id
            WHERE a.status = 'selected'
              AND p.status IN ('open', 'in_progress')
              AND p.latitude  BETWEEN %s AND %s
              AND p.longitude BETWEEN %s AND %s
            """,
            (min_lat, max_lat, min_lng, max_lng),
            fetch="all"
        )

        connections = [
            {
                "post_id":    str(c["post_id"]),
                "worker_id":  str(c["worker_id"]),
                "post_lat":   float(c["post_lat"])   if c["post_lat"]   else None,
                "post_lng":   float(c["post_lng"])   if c["post_lng"]   else None,
                "worker_lat": float(c["worker_lat"]) if c["worker_lat"] else None,
                "worker_lng": float(c["worker_lng"]) if c["worker_lng"] else None,
            }
            for c in (connections_raw or [])
            if c["post_lat"] and c["post_lng"] and c["worker_lat"] and c["worker_lng"]
        ]

        return {
            "posts":       posts,
            "workers":     workers,
            "connections": connections,
            "mode":        "gps",
            "radius_km":   radius_km,
        }

    # ─── District Fallback Mode ────────────────────────────────────────────────
    @staticmethod
    async def get_map_district(district, current_user_id, db):
        posts_raw = execute_query(
            db,
            """
            SELECT p.*,
                   u.name     AS poster_name,
                   u.photo_url AS poster_photo,
                   u.trust_score AS poster_trust
            FROM posts p
            JOIN users u ON u.id = p.poster_id
            WHERE p.status    = 'open'
              AND p.district  = %s
              AND p.poster_id != %s
            ORDER BY p.created_at DESC
            LIMIT 30
            """,
            (district, current_user_id),
            fetch="all"
        )

        posts = ExploreService._enrich_posts(posts_raw, None, None, db)

        return {
            "posts":       posts,
            "workers":     [],
            "connections": [],
            "mode":        "district",
            "radius_km":   None,
        }

    # ─── Enrich Posts ─────────────────────────────────────────────────────────
    @staticmethod
    def _enrich_posts(posts_raw, user_lat, user_lng, db):
        enriched = []
        for p in (posts_raw or []):
            # Applications count
            app_count = execute_query(
                db,
                "SELECT COUNT(*) AS count FROM applications WHERE post_id = %s AND status != 'withdrawn'",
                (str(p["id"]),),
                fetch="one"
            )

            # Poster rating (as a poster / client)
            poster_rating_row = execute_query(
                db,
                """
                SELECT ROUND(AVG(stars)::numeric, 1) AS avg
                FROM ratings
                WHERE rated_id = %s
                  AND rating_type = 'worker_to_client'
                  AND is_revealed = true
                """,
                (str(p["poster_id"]),),
                fetch="one"
            )
            poster_rating = (
                float(poster_rating_row["avg"])
                if poster_rating_row and poster_rating_row["avg"]
                else None
            )

            # Distance
            distance_km = None
            if (user_lat is not None and user_lng is not None
                    and p.get("latitude") and p.get("longitude")):
                distance_km = FeedService.calculate_distance_km(
                    user_lat, user_lng,
                    p["latitude"], p["longitude"]
                )

            enriched.append({
                "id":              str(p["id"]),
                "title":           p["title"],
                "description":     p["description"],
                "post_category":   p.get("post_category"),
                "job_nature":      p.get("job_nature"),
                "task_type":       p.get("task_type"),
                "pay_per_person":  p.get("pay_per_person"),
                "workers_needed":  p.get("workers_needed"),
                "slots_remaining": p.get("slots_remaining"),
                "no_exp_needed":   p.get("no_exp_needed", False),
                "urgency_tag":     p.get("urgency_tag"),
                "status":          p.get("status"),
                "latitude":        float(p["latitude"])  if p.get("latitude")  else None,
                "longitude":       float(p["longitude"]) if p.get("longitude") else None,
                "area_name":       p.get("area_name"),
                "district":        p.get("district"),
                "distance_km":     distance_km,
                "work_date":       p["work_date"].isoformat() if p.get("work_date") else None,
                "work_time_slot":  p.get("work_time_slot"),
                "tags":            p.get("tags") or [],
                "applications_count": app_count["count"] if app_count else 0,
                "created_at":      p["created_at"].isoformat() if p.get("created_at") else None,
                "poster": {
                    "id":            str(p["poster_id"]),
                    "name":          p.get("poster_name"),
                    "photo_url":     p.get("poster_photo"),
                    "poster_rating": poster_rating,
                },
            })
        return enriched

    # ─── Enrich Workers ───────────────────────────────────────────────────────
    @staticmethod
    def _enrich_workers(workers_raw, user_lat, user_lng):
        result = []
        for w in (workers_raw or []):
            distance_km = None
            if (user_lat is not None and user_lng is not None
                    and w.get("latitude") and w.get("longitude")):
                distance_km = FeedService.calculate_distance_km(
                    user_lat, user_lng,
                    w["latitude"], w["longitude"]
                )
            result.append({
                "id":         str(w["id"]),
                "name":       w.get("name"),
                "photo_url":  w.get("photo_url"),
                "trust_score": w.get("trust_score"),
                "trust_badge": w.get("trust_badge"),
                "latitude":   float(w["latitude"])  if w.get("latitude")  else None,
                "longitude":  float(w["longitude"]) if w.get("longitude") else None,
                "skills":     w.get("skills") or [],
                "wage_min":   w.get("wage_min"),
                "wage_max":   w.get("wage_max"),
                "distance_km": distance_km,
            })
        return result
