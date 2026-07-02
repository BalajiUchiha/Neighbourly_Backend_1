from fastapi import APIRouter, Depends, Request, Query
from controllers.rag_controller import RagController
from database import get_db
from utils.dependencies import get_current_user

router = APIRouter()

@router.get("/session")
async def get_or_init_session(
    post_id: str = Query(...),
    worker_id: str = Query(...),
    db=Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    return await RagController.get_or_init_session(
        post_id, worker_id, current_user_id, db
    )

@router.post("/ask")
async def ask(
    request: Request,
    db=Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    return await RagController.ask(request, current_user_id, db)

@router.get("/history")
async def get_history(
    post_id: str = Query(...),
    db=Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    return await RagController.get_history(post_id, current_user_id, db)

@router.post("/invite")
async def invite_worker(
    request: Request,
    db=Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    return await RagController.invite_worker(request, current_user_id, db)