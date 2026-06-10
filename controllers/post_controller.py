from fastapi import HTTPException
from services.post_service import PostService
from services.ai_service import AIService
import json

class PostController:

    @staticmethod
    async def ai_refine(request, current_user_id, db):
        body = await request.json()
        raw_input = body.get("raw_input", "").strip()
        if not raw_input:
            raise HTTPException(400, "raw_input is required")
        try:
            result = await AIService.refine_post(
                raw_input=raw_input,
                retry_reason=body.get("retry_reason"),
                previous_result=body.get("previous_result")
            )
            return {"result": result}
        except Exception as e:
            raise HTTPException(500, f"AI refinement failed: {str(e)}")

    @staticmethod
    async def create_post(
        ai_result_str, additional_details_str,
        raw_input, input_method, images,
        current_user_id, db
    ):
        try:
            ai_result = json.loads(ai_result_str)
            additional_details = json.loads(additional_details_str)
        except Exception:
            raise HTTPException(400, "Invalid JSON in ai_result or additional_details")

        return await PostService.create_post(
            ai_result, additional_details,
            raw_input, input_method,
            images, current_user_id, db
        )

    @staticmethod
    async def my_active_post(current_user_id, db):
        return await PostService.get_my_active_post(current_user_id, db)
