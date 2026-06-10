from fastapi import HTTPException, Response, Request
from services.auth_service import AuthService

class AuthController:

    @staticmethod
    async def login(request: Request, response: Response, db):
        body = await request.json()
        identifier = body.get("identifier")
        password = body.get("password")
        if not identifier or not password:
            raise HTTPException(400, "Identifier and password required")
        return await AuthService.login(identifier, password, response, db, request)

    @staticmethod
    async def signup(request: Request, response: Response, db):
        body = await request.json()
        return await AuthService.signup(body, response, db, request)

    @staticmethod
    async def check_username(username: str, db):
        return await AuthService.check_username(username, db)

    @staticmethod
    async def refresh(request: Request, response: Response, db):
        return await AuthService.refresh(request, response, db)

    @staticmethod
    async def logout(request: Request, response: Response, db):
        return await AuthService.logout(request, response, db)
