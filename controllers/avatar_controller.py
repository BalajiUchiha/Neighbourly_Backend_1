from fastapi import HTTPException
from services.avatar_service import AvatarService

class AvatarController:

    @staticmethod
    async def explain(request, current_user_id, db):
        body = await request.json()
        if not body.get("selected_content"):
            raise HTTPException(400, "selected_content is required")
        return await AvatarService.explain(
            selected_content=body.get("selected_content"),
            specific_question=body.get("specific_question"),
            screen_context=body.get("screen_context", "/home"),
            language=body.get("language", "english"),
            session_id=body.get("session_id"),
            current_user_id=current_user_id,
            db=db
        )

    @staticmethod
    async def reprocess_reply(request, current_user_id, db):
        body = await request.json()
        return await AvatarService.reprocess_reply(
            original_reply=body.get("original_reply", ""),
            session_id=body.get("session_id"),
            language=body.get("language", "english")
        )

    @staticmethod
    async def get_audio(type, language):
        return await AvatarService.get_pre_written_audio(type, language)

    @staticmethod
    async def get_history(current_user_id, db):
        return await AvatarService.get_history(current_user_id, db)

    @staticmethod
    async def execute_action(request, current_user_id, db):
        body = await request.json()
        return await AvatarService.execute_action(
            session_id=body.get("session_id"),
            action_type=body.get("action_type"),
            action_reference_id=body.get("action_reference_id"),
            current_user_id=current_user_id,
            db=db
        )