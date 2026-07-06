from fastapi import APIRouter, Depends, Request
from controllers.application_controller import ApplicationController
from database import get_db
from utils.dependencies import get_current_user

router = APIRouter()

@router.get("/{post_id}")
async def get_applicants(
    post_id: str,
    db=Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    return await ApplicationController.get_applicants(post_id, current_user_id, db)

@router.post("/apply")
async def apply(
    request: Request,
    db=Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    body = await request.json()
    return await ApplicationController.apply(body, current_user_id, db)

@router.patch("/{application_id}/select")
async def select_applicant(
    application_id: str,
    db=Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    return await ApplicationController.select_applicant(application_id, current_user_id, db)

@router.patch("/{application_id}/reject")
async def reject_applicant(
    application_id: str,
    db=Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    return await ApplicationController.reject_applicant(application_id, current_user_id, db)
