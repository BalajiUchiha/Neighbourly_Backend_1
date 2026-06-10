from database import execute_query, connection_pool
from datetime import datetime, timedelta
import uuid

class RadiusService:

    @staticmethod
    async def expand_radii():
        """
        Background job: expand post search radius for posts with no applicants.
        For every open post older than 24h with no applicants and room to expand:
          - Expand current_radius_km by 10 (capped at max_radius_km)
          - Update expansion_count
          - If new radius hits max, set is_remote_area = True
          - Log a row in radius_expansions
        """
        conn = connection_pool.getconn()
        try:
            now = datetime.utcnow()
            cutoff = now - timedelta(hours=24)

            candidates = execute_query(
                conn,
                """SELECT * FROM posts 
                   WHERE status = 'open'
                   AND created_at < %s
                   AND current_radius_km < max_radius_km
                   AND (last_radius_expanded_at IS NULL OR last_radius_expanded_at < %s)""",
                (cutoff, cutoff),
                fetch="all"
            )

            for post in (candidates or []):
                # Count active applications
                app_count = execute_query(
                    conn,
                    "SELECT COUNT(*) as count FROM applications WHERE post_id = %s AND status != 'withdrawn'",
                    (str(post["id"]),),
                    fetch="one"
                )

                if app_count and app_count["count"] > 0:
                    continue

                old_radius = post["current_radius_km"] or 0.0
                new_radius = min(old_radius + 10.0, post["max_radius_km"])
                is_remote = new_radius >= post["max_radius_km"]

                # Update post
                execute_query(
                    conn,
                    """UPDATE posts 
                       SET current_radius_km = %s,
                           last_radius_expanded_at = %s,
                           expansion_count = COALESCE(expansion_count, 0) + 1,
                           is_remote_area = %s
                       WHERE id = %s""",
                    (new_radius, now, is_remote, post["id"])
                )

                # Log expansion
                execute_query(
                    conn,
                    """INSERT INTO radius_expansions 
                       (id, post_id, old_radius_km, new_radius_km, applicant_count_at_expansion, expanded_at)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (str(uuid.uuid4()), str(post["id"]), old_radius, new_radius, 0, now)
                )

            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"[RadiusService] expand_radii error: {e}")
        finally:
            connection_pool.putconn(conn)
