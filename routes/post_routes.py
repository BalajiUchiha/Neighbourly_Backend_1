from fastapi import APIRouter, Depends, Request, UploadFile, File, Form
from controllers.post_controller import PostController
from database import get_db
from utils.dependencies import get_current_user
from typing import Optional, List

router = APIRouter()

@router.post("/ai-refine")
async def ai_refine(
    request: Request,
    db=Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    return await PostController.ai_refine(request, current_user_id, db)

@router.post("/create")
async def create_post(
    ai_result: str = Form(...),
    additional_details: str = Form(...),
    raw_input: str = Form(...),
    input_method: str = Form(...),
    image_0: Optional[UploadFile] = File(None),
    image_1: Optional[UploadFile] = File(None),
    image_2: Optional[UploadFile] = File(None),
    db=Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    images = [img for img in [image_0, image_1, image_2] if img]
    return await PostController.create_post(
        ai_result, additional_details, raw_input,
        input_method, images, current_user_id, db
    )

@router.get("/my-active")
async def my_active_post(
    db=Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    return await PostController.my_active_post(current_user_id, db)
