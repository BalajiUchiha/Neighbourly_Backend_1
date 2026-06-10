from services.feed_service import FeedService

class FeedController:

    @staticmethod
    async def get_feed(filter, radius, current_user_id, db):
        return await FeedService.get_feed(filter, radius, current_user_id, db)

    @staticmethod
    async def get_active_post(current_user_id, db):
        return await FeedService.get_active_post(current_user_id, db)

    @staticmethod
    async def update_location(body, current_user_id, db):
        return await FeedService.update_location(body, current_user_id, db)
