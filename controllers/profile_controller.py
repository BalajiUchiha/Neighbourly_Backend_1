from services.profile_service import ProfileService

class ProfileController:
    @staticmethod
    async def get_profile_me(current_user_id: str, db):
        return await ProfileService.get_profile_me(current_user_id, db)

    @staticmethod
    async def get_my_posts(current_user_id: str, db):
        return await ProfileService.get_my_posts(current_user_id, db)

    @staticmethod
    async def update_profile(current_user_id: str, body: dict, db):
        return await ProfileService.update_profile(current_user_id, body, db)

    @staticmethod
    async def update_worker(current_user_id: str, body: dict, db):
        return await ProfileService.update_worker(current_user_id, body, db)

    @staticmethod
    async def update_location(current_user_id: str, body: dict, db):
        return await ProfileService.update_location(current_user_id, body, db)
