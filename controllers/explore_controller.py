from services.explore_service import ExploreService


class ExploreController:

    @staticmethod
    async def get_map(lat, lng, radius, district, filter_type, current_user_id, db):
        return await ExploreService.get_map(
            lat=lat,
            lng=lng,
            radius_km=radius,
            district=district,
            filter_type=filter_type,
            current_user_id=current_user_id,
            db=db,
        )
