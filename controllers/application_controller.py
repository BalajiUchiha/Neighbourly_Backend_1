from services.application_service import ApplicationService

class ApplicationController:

    @staticmethod
    async def get_applicants(post_id: str, current_user_id: str, db):
        return await ApplicationService.get_applicants(post_id, current_user_id, db)

    @staticmethod
    async def apply(body: dict, current_user_id: str, db):
        return await ApplicationService.apply(body, current_user_id, db)

    @staticmethod
    async def select_applicant(application_id: str, current_user_id: str, db):
        return await ApplicationService.select_applicant(application_id, current_user_id, db)

    @staticmethod
    async def reject_applicant(application_id: str, current_user_id: str, db):
        return await ApplicationService.reject_applicant(application_id, current_user_id, db)
