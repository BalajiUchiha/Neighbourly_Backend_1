from fastapi import APIRouter, Depends, Request, Query
from controllers.avatar_controller import AvatarController
from database import get_db
from utils.dependencies import get_current_user

router = APIRouter()

@router.post("/explain")
async def explain(
    request: Request,
    db=Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    return await AvatarController.explain(request, current_user_id, db)

@router.get("/audio")
async def get_audio(
    type: str = Query(...),
    language: str = Query(default="english"),
    db=Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    return await AvatarController.get_audio(type, language)

@router.get("/history")
async def get_history(
    db=Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    return await AvatarController.get_history(current_user_id, db)

@router.post("/action")
async def execute_action(
    request: Request,
    db=Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    return await AvatarController.execute_action(request, current_user_id, db)