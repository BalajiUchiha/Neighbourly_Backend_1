from fastapi import APIRouter, Depends, Response, Request
from controllers.auth_controller import AuthController
from database import get_db

router = APIRouter()

@router.post("/login")
async def login(request: Request, response: Response, db=Depends(get_db)):
    return await AuthController.login(request, response, db)

@router.post("/signup")
async def signup(request: Request, response: Response, db=Depends(get_db)):
    return await AuthController.signup(request, response, db)

@router.get("/check-username")
async def check_username(username: str, db=Depends(get_db)):
    return await AuthController.check_username(username, db)

@router.post("/refresh")
async def refresh(request: Request, response: Response, db=Depends(get_db)):
    return await AuthController.refresh(request, response, db)

@router.post("/logout")
async def logout(request: Request, response: Response, db=Depends(get_db)):
    return await AuthController.logout(request, response, db)
