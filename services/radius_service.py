import uuid
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from models.post import Post
from models.application import Application
from models.radius_expansion import RadiusExpansion


class RadiusService:
    """Background job: expand post search radius for posts with no applicants."""

    async def expand_radii(self, db: Session) -> None:
        """
        For every open post older than 24 h with no applicants and room to expand:
          - Expand current_radius_km by 10 (capped at max_radius_km)
          - Update last_radius_expanded_at and expansion_count
          - If new radius hits max, set is_remote_area = True
          - Log a row in radius_expansions
        All writes committed in a single transaction.
        """
        now = datetime.utcnow()
        cutoff = now - timedelta(hours=24)

        candidates = (
            db.query(Post)
            .filter(
                Post.status == "open",
                Post.created_at < cutoff,
                Post.current_radius_km < Post.max_radius_km,
            )
            .filter(
                (Post.last_radius_expanded_at == None) |
                (Post.last_radius_expanded_at < cutoff)
            )
            .all()
        )

        for post in candidates:
            # Count active applications (excluding withdrawn)
            applicant_count = (
                db.query(Application)
                .filter(
                    Application.post_id == post.id,
                    Application.status != "withdrawn",
                )
                .count()
            )

            # Skip posts that already have applicants
            if applicant_count > 0:
                continue

            old_radius = post.current_radius_km or 0.0
            new_radius = min(old_radius + 10.0, post.max_radius_km)

            # Update post
            post.current_radius_km = new_radius
            post.last_radius_expanded_at = now
            post.expansion_count = (post.expansion_count or 0) + 1
            if new_radius >= post.max_radius_km:
                post.is_remote_area = True

            # Log expansion
            db.add(
                RadiusExpansion(
                    id=uuid.uuid4(),
                    post_id=post.id,
                    old_radius_km=old_radius,
                    new_radius_km=new_radius,
                    applicant_count_at_expansion=applicant_count,
                    expanded_at=now,
                )
            )

        db.commit()
