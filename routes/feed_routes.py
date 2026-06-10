from fastapi import APIRouter, Depends, Request, Query
from controllers.feed_controller import FeedController
from database import get_db
from utils.dependencies import get_current_user

router = APIRouter()

@router.get("")
async def get_feed(
    filter: str = Query(default="all"),
    radius: float = Query(default=15),
    db=Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    return await FeedController.get_feed(filter, radius, current_user_id, db)

@router.get("/active-post")
async def get_active_post(
    db=Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    return await FeedController.get_active_post(current_user_id, db)

@router.patch("/location")
async def update_location(
    request: Request,
    db=Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    body = await request.json()
    return await FeedController.update_location(body, current_user_id, db)
