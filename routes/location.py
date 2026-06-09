from fastapi import APIRouter, HTTPException
from schemas.auth import ReverseGeocodeRequest
from utils.location import reverse_geocode
from utils.india_districts import INDIAN_DISTRICTS

router = APIRouter(tags=["location"])


@router.post("/reverse-geocode")
async def reverse_geocode_endpoint(body: ReverseGeocodeRequest):
    """
    Perform reverse geocoding on a set of latitude/longitude coordinates.
    """
    return await reverse_geocode(body.latitude, body.longitude)


@router.get("/districts")
async def get_districts():
    """
    Fetch the static list of Indian districts.
    """
    return {"districts": INDIAN_DISTRICTS}
