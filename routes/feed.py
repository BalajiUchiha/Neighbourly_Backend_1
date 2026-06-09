from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from database import get_db
from utils.dependencies import get_current_user
from services.feed_service import FeedService
from models.user import User

router = APIRouter(tags=["feed"])

_feed_service = FeedService()


# ---------------------------------------------------------------------------
# GET /api/feed
# ---------------------------------------------------------------------------
@router.get("")
async def get_feed(
    filter: str = "all",
    radius: float = 15.0,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
):
    """
    Return home-screen feed posts filtered by the requested filter tab.
    Query params:
      - filter: all | for_me | part_time | volunteer | no_exp | urgent  (default: all)
      - radius: search radius in km                                       (default: 15)
    """
    return _feed_service.get_feed(
        db=db,
        current_user_id=current_user_id,
        filter_name=filter,
        radius_km=radius,
    )


# ---------------------------------------------------------------------------
# GET /api/feed/active-post
# ---------------------------------------------------------------------------
@router.get("/active-post")
async def get_active_post(
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
):
    """
    Return the current user's most recent open post enriched with suggested workers,
    or null if they have no open post.
    """
    result = _feed_service.get_active_post(db=db, current_user_id=current_user_id)
    return {"post": result}


# ---------------------------------------------------------------------------
# PATCH /api/feed/location
# ---------------------------------------------------------------------------
class LocationBody(BaseModel):
    latitude: float
    longitude: float


@router.patch("/location")
async def update_location(
    body: LocationBody,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
):
    """
    Silently update the authenticated user's lat/lng and updated_at.
    Returns 200 with no content payload.
    """
    user: Optional[User] = db.query(User).filter(User.id == current_user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.latitude = str(body.latitude)
    user.longitude = str(body.longitude)
    user.updated_at = datetime.utcnow()
    db.commit()

    return {"status": "ok"}
