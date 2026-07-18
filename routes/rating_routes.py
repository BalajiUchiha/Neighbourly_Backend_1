from fastapi import APIRouter, Depends, Request
from controllers.rating_controller import RatingController
from database import get_db
from utils.dependencies import get_current_user

router = APIRouter()

@router.get("/context/{chat_id}")
async def get_rating_context(
    chat_id: str,
    db=Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    return await RatingController.get_rating_context(chat_id, current_user_id, db)

@router.post("/submit")
async def submit_rating(
    request: Request,
    db=Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    body = await request.json()
    return await RatingController.submit_rating(current_user_id, body, db)

@router.get("/trust-score")
async def get_trust_score(
    db=Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    return await RatingController.get_trust_score(current_user_id, db)

@router.get("/my-reviews")
async def get_my_reviews(
    db=Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    return await RatingController.get_my_reviews(current_user_id, db)
