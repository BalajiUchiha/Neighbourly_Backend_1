from fastapi import HTTPException
from services.rag_service import RagService

class RagController:

    @staticmethod
    async def get_or_init_session(post_id, worker_id, current_user_id, db):
        return await RagService.get_or_init_session(
            post_id, worker_id, current_user_id, db
        )

    @staticmethod
    async def ask(request, current_user_id, db):
        body = await request.json()
        question = body.get("question", "").strip()
        if not question:
            raise HTTPException(400, "Question is required")
        return await RagService.ask(
            post_id=body.get("post_id"),
            worker_id=body.get("worker_id"),
            question=question,
            session_id=body.get("session_id"),
            source=body.get("source", "rag_suggestion"),
            current_user_id=current_user_id,
            db=db
        )

    @staticmethod
    async def get_history(post_id, current_user_id, db):
        return await RagService.get_history(post_id, current_user_id, db)

    @staticmethod
    async def invite_worker(request, current_user_id, db):
        body = await request.json()
        return await RagService.invite_worker(
            post_id=body.get("post_id"),
            worker_id=body.get("worker_id"),
            session_id=body.get("session_id"),
            current_user_id=current_user_id,
            db=db
        )