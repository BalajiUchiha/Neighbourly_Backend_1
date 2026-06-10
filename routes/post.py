from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from database import get_db
from routes.auth import get_current_user
from schemas.post import AIRefineRequest, AIRefineResult, PostCreateRequest
from services.ai_service import AIService
from services.post_service import PostService
from models.post import Post, PostImage
import json
from typing import List

router = APIRouter()

@router.post("/ai-refine")
async def ai_refine(request: AIRefineRequest, current_user = Depends(get_current_user)):
    try:
        result = await AIService.refine_post(
            raw_input=request.raw_input,
            retry_reason=request.retry_reason,
            previous_result=request.previous_result,
            preferred_language=request.preferred_language
        )
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail="AI refinement failed, please try again")

@router.post("/create")
async def create_post(
    ai_result: str = Form(...),
    additional_details: str = Form(...),
    raw_input: str = Form(...),
    input_method: str = Form(...),
    image_0: UploadFile = File(None),
    image_1: UploadFile = File(None),
    image_2: UploadFile = File(None),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        ai_res_dict = json.loads(ai_result)
        add_details_dict = json.loads(additional_details)
        
        files_to_upload = [f for f in [image_0, image_1, image_2] if f is not None]
        image_urls = PostService.upload_images(files_to_upload)
        
        post_id, post = PostService.create_post(
            db=db,
            current_user=current_user,
            ai_result=ai_res_dict,
            additional_details=add_details_dict,
            raw_input=raw_input,
            input_method=input_method,
            image_urls=image_urls
        )
        
        return {
            "post_id": post_id,
            "post": {
                "id": post.id,
                "title": post.title,
                "description": post.description,
                "task_type": post.task_type
            },
            "message": "Post created successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create post: {str(e)}")

@router.get("/my-active")
def get_my_active_post(current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    post = db.query(Post).filter(
        Post.poster_id == current_user.id,
        Post.status == "open"
    ).order_by(Post.created_at.desc()).first()
    
    if not post:
        return {"post": None}
        
    return {"post": post}
