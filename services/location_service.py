from utils.location import reverse_geocode
from utils.india_districts import INDIAN_DISTRICTS

class LocationService:

    @staticmethod
    async def reverse_geocode(latitude, longitude):
        return await reverse_geocode(latitude, longitude)

    @staticmethod
    def get_districts():
        return {"districts": INDIAN_DISTRICTS}
