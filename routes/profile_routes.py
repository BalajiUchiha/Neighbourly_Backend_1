from fastapi import APIRouter, Depends, Request
from controllers.profile_controller import ProfileController
from database import get_db
from utils.dependencies import get_current_user

router = APIRouter()

@router.get("/me")
async def get_profile_me(
    db=Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    return await ProfileController.get_profile_me(current_user_id, db)

@router.get("/my-posts")
async def get_my_posts(
    db=Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    return await ProfileController.get_my_posts(current_user_id, db)

@router.patch("/update")
async def update_profile(
    request: Request,
    db=Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    body = await request.json()
    return await ProfileController.update_profile(current_user_id, body, db)

@router.patch("/update-worker")
async def update_worker(
    request: Request,
    db=Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    body = await request.json()
    return await ProfileController.update_worker(current_user_id, body, db)

@router.patch("/update-location")
async def update_location(
    request: Request,
    db=Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    body = await request.json()
    return await ProfileController.update_location(current_user_id, body, db)
