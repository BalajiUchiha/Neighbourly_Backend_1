from fastapi import APIRouter, Depends, Request
from controllers.location_controller import LocationController
from database import get_db

router = APIRouter()

@router.post("/reverse-geocode")
async def reverse_geocode(request: Request):
    return await LocationController.reverse_geocode(request)

@router.get("/districts")
async def get_districts():
    return await LocationController.get_districts()
