from math import radians, cos, sqrt
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from models.post import Post, PostImage
from models.application import Application
from models.rating import Rating
from models.user import User
from models.worker import WorkerProfile


# ---------------------------------------------------------------------------
# Geo helpers
# ---------------------------------------------------------------------------

def get_bounding_box(lat: float, lng: float, radius_km: float):
    """Return (min_lat, max_lat, min_lng, max_lng) for a square bounding box."""
    delta_lat = radius_km / 111.0
    delta_lng = radius_km / (111.0 * abs(cos(radians(lat))))
    min_lat = lat - delta_lat
    max_lat = lat + delta_lat
    min_lng = lng - delta_lng
    max_lng = lng + delta_lng
    return min_lat, max_lat, min_lng, max_lng


def calculate_distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Flat-earth approximation — good enough for hyperlocal distances."""
    dlat = (lat2 - lat1) * 111.0
    dlng = (lng2 - lng1) * 111.0 * abs(cos(radians(lat1)))
    return round(sqrt(dlat ** 2 + dlng ** 2), 1)


# ---------------------------------------------------------------------------
# Urgency ordering helper
# ---------------------------------------------------------------------------
URGENCY_ORDER = {"today": 0, "tomorrow": 1, "this_week": 2, "flexible": 3}


def urgency_sort_key(post: Post) -> int:
    return URGENCY_ORDER.get(post.urgency_tag or "flexible", 3)


# ---------------------------------------------------------------------------
# FeedService
# ---------------------------------------------------------------------------

class FeedService:
    """Core feed retrieval and enrichment logic."""

    # ------------------------------------------------------------------
    # Public: get_feed
    # ------------------------------------------------------------------
    def get_feed(
        self,
        db: Session,
        current_user_id: str,
        filter_name: str = "all",
        radius_km: float = 15.0,
    ) -> dict:
        user: Optional[User] = db.query(User).filter(User.id == current_user_id).first()
        if not user:
            return {"posts": [], "total": 0, "radius_km": radius_km, "filter": filter_name}

        # Parse GPS coords
        lat = self._parse_float(user.latitude)
        lng = self._parse_float(user.longitude)
        has_gps = lat is not None and lng is not None

        # Fallback: no location at all
        if not has_gps and not user.district:
            return {
                "posts": [],
                "total": 0,
                "radius_km": radius_km,
                "filter": filter_name,
                "message": "No location data found. Please update your location.",
            }

        # Build base query
        query = (
            db.query(Post)
            .filter(Post.status == "open")
            .filter(Post.poster_id != current_user_id)
        )

        if has_gps:
            min_lat, max_lat, min_lng, max_lng = get_bounding_box(lat, lng, radius_km)
            # Fetch candidates with non-null coordinates then filter in Python
            # (avoids dialect-specific float casting for string lat/lng columns)
            posts_raw = query.filter(
                Post.latitude.isnot(None),
                Post.longitude.isnot(None),
            ).all()
            posts_raw = [
                p for p in posts_raw
                if (plat := self._parse_float(p.latitude)) is not None
                and (plng := self._parse_float(p.longitude)) is not None
                and min_lat <= plat <= max_lat
                and min_lng <= plng <= max_lng
            ]
        else:
            # District-only filter
            query = query.filter(Post.district == user.district)
            posts_raw = query.all()

        # Apply per-filter logic
        posts_raw = self._apply_filter(
            posts_raw, filter_name, user, db, has_gps, current_user_id
        )

        # Limit
        posts_raw = posts_raw[:20]

        # Enrich
        enriched = [
            self._enrich_post(p, db, user_id=current_user_id, user_lat=lat, user_lng=lng, is_own=False)
            for p in posts_raw
        ]

        return {
            "posts": enriched,
            "total": len(enriched),
            "radius_km": radius_km,
            "filter": filter_name,
        }

    # ------------------------------------------------------------------
    # Public: get_active_post
    # ------------------------------------------------------------------
    def get_active_post(self, db: Session, current_user_id: str) -> Optional[dict]:
        post: Optional[Post] = (
            db.query(Post)
            .filter(Post.poster_id == current_user_id, Post.status == "open")
            .order_by(Post.created_at.desc())
            .first()
        )
        if not post:
            return None

        enriched = self._enrich_post(post, db, user_id=current_user_id, user_lat=None, user_lng=None, is_own=True)

        # Suggested workers: same district, is_worker=true, order by trust_score desc, limit 5
        suggested = []
        if post.district:
            workers = (
                db.query(User)
                .join(WorkerProfile, WorkerProfile.user_id == User.id)
                .filter(User.district == post.district, User.is_worker == True)
                .order_by(User.trust_score.desc())
                .limit(5)
                .all()
            )
            suggested = [
                {
                    "id": str(w.id),
                    "name": w.name,
                    "username": w.username,
                    "photo_url": w.photo_url,
                    "trust_score": w.trust_score,
                    "trust_badge": w.trust_badge,
                    "district": w.district,
                }
                for w in workers
            ]

        enriched["suggested_workers"] = suggested
        return enriched

    # ------------------------------------------------------------------
    # Private: filter dispatch
    # ------------------------------------------------------------------
    def _apply_filter(
        self, posts: list, filter_name: str, user: User, db: Session, has_gps: bool, current_user_id: str
    ) -> list:
        if filter_name == "all":
            posts.sort(key=lambda p: (urgency_sort_key(p), p.created_at or datetime.min))
            return posts

        if filter_name == "for_me":
            worker_profile: Optional[WorkerProfile] = (
                db.query(WorkerProfile)
                .filter(WorkerProfile.user_id == current_user_id)
                .first()
            )
            if worker_profile and worker_profile.skills:
                skills = worker_profile.skills if isinstance(worker_profile.skills, list) else []
                posts = [p for p in posts if p.task_type in skills]
            else:
                # Fallback: same district
                posts = [p for p in posts if p.district == user.district]
            posts.sort(key=lambda p: (urgency_sort_key(p), p.created_at or datetime.min))
            return posts

        if filter_name == "part_time":
            posts = [p for p in posts if p.job_nature == "part_time"]
            posts.sort(key=lambda p: (-(p.pay_per_person or 0)))
            return posts

        if filter_name == "volunteer":
            posts = [p for p in posts if p.post_category == "volunteer"]
            posts.sort(key=lambda p: p.work_date or datetime.max.date())
            return posts

        if filter_name == "no_exp":
            posts = [p for p in posts if p.no_exp_needed]
            posts.sort(key=lambda p: (urgency_sort_key(p), p.created_at or datetime.min))
            return posts

        if filter_name == "urgent":
            posts = [p for p in posts if p.urgency_tag in ("today", "tomorrow")]
            posts.sort(key=lambda p: urgency_sort_key(p))
            return posts

        # Default: same as all
        posts.sort(key=lambda p: (urgency_sort_key(p), p.created_at or datetime.min))
        return posts

    # ------------------------------------------------------------------
    # Private: enrich a single post
    # ------------------------------------------------------------------
    def _enrich_post(
        self,
        post: Post,
        db: Session,
        user_id: str,
        user_lat: Optional[float],
        user_lng: Optional[float],
        is_own: bool,
    ) -> dict:
        # Poster info
        poster = db.query(User).filter(User.id == post.poster_id).first()
        poster_obj = None
        if poster:
            poster_obj = {
                "id": str(poster.id),
                "name": poster.name,
                "photo_url": poster.photo_url,
            }

        # Ratings (revealed only)
        worker_ratings = (
            db.query(Rating)
            .filter(Rating.ratee_id == post.poster_id, Rating.rating_type == "worker_rating", Rating.is_revealed == True)
            .all()
        )
        poster_ratings = (
            db.query(Rating)
            .filter(Rating.ratee_id == post.poster_id, Rating.rating_type == "poster_rating", Rating.is_revealed == True)
            .all()
        )
        worker_avg = (
            round(sum(r.score for r in worker_ratings) / len(worker_ratings), 1)
            if worker_ratings else None
        )
        poster_avg = (
            round(sum(r.score for r in poster_ratings) / len(poster_ratings), 1)
            if poster_ratings else None
        )

        # Images ordered by display_order
        images = (
            db.query(PostImage)
            .filter(PostImage.post_id == post.id)
            .order_by(PostImage.display_order.asc())
            .all()
        )
        images_list = [
            {"id": str(img.id), "image_url": img.image_url, "display_order": img.display_order}
            for img in images
        ]

        # Application count (excluding withdrawn)
        app_count = (
            db.query(Application)
            .filter(Application.post_id == post.id, Application.status != "withdrawn")
            .count()
        )

        # Distance
        distance_km = None
        if user_lat is not None and user_lng is not None:
            post_lat = self._parse_float(post.latitude)
            post_lng = self._parse_float(post.longitude)
            if post_lat is not None and post_lng is not None:
                distance_km = calculate_distance_km(user_lat, user_lng, post_lat, post_lng)

        return {
            "id": str(post.id),
            "poster_id": str(post.poster_id),
            "poster": poster_obj,
            "title": post.title,
            "description": post.description,
            "task_type": post.task_type,
            "post_category": post.post_category,
            "workers_needed": post.workers_needed,
            "slots_remaining": post.slots_remaining,
            "pay_per_person": post.pay_per_person,
            "no_exp_needed": post.no_exp_needed,
            "job_nature": post.job_nature,
            "urgency_tag": post.urgency_tag,
            "status": post.status,
            "area_name": post.area_name,
            "district": post.district,
            "distance_km": distance_km,
            "work_date": post.work_date.isoformat() if post.work_date else None,
            "work_time_slot": post.work_time_slot,
            "tags": post.tags if isinstance(post.tags, list) else [],
            "raw_input_text": post.raw_input_text,
            "has_voice_input": post.has_voice_input,
            "images": images_list,
            "applications_count": app_count,
            "worker_rating_avg": worker_avg,
            "poster_rating_avg": poster_avg,
            "suggested_workers": None,  # populated only for is_own_post
            "created_at": post.created_at.isoformat() if post.created_at else None,
            "is_own_post": is_own,
        }

    # ------------------------------------------------------------------
    # Private: safe float parse
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_float(value) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
