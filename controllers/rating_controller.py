from services.rating_service import RatingService

class RatingController:
    @staticmethod
    async def get_rating_context(chat_id: str, current_user_id: str, db):
        return await RatingService.get_rating_context(chat_id, current_user_id, db)

    @staticmethod
    async def submit_rating(current_user_id: str, body: dict, db):
        return await RatingService.submit_rating(current_user_id, body, db)

    @staticmethod
    async def get_trust_score(current_user_id: str, db):
        return await RatingService.get_trust_score(current_user_id, db)

    @staticmethod
    async def get_my_reviews(current_user_id: str, db):
        return await RatingService.get_my_reviews(current_user_id, db)
