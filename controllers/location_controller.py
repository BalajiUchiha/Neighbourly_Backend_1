from services.location_service import LocationService

class LocationController:

    @staticmethod
    async def reverse_geocode(request):
        body = await request.json()
        latitude = body.get("latitude")
        longitude = body.get("longitude")
        return await LocationService.reverse_geocode(latitude, longitude)

    @staticmethod
    async def get_districts():
        return LocationService.get_districts()
