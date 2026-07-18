from fastapi import APIRouter, Depends
from controllers.notification_controller import NotificationController
from database import get_db
from utils.dependencies import get_current_user

router = APIRouter()

@router.get("")
async def get_all(
    db=Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    return await NotificationController.get_all(current_user_id, db)

@router.get("/unread-count")
async def get_unread_count(
    db=Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    return await NotificationController.get_unread_count(current_user_id, db)

@router.patch("/{notification_id}/read")
async def mark_read(
    notification_id: str,
    db=Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    return await NotificationController.mark_read(notification_id, current_user_id, db)

@router.patch("/mark-all-read")
async def mark_all_read(
    db=Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    return await NotificationController.mark_all_read(current_user_id, db)

@router.delete("/{notification_id}")
async def delete(
    notification_id: str,
    db=Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    return await NotificationController.delete(notification_id, current_user_id, db)
