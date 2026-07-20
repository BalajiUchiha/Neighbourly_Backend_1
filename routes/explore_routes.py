from fastapi import APIRouter, Depends, Query
from typing import Optional
from controllers.explore_controller import ExploreController
from database import get_db
from utils.dependencies import get_current_user

router = APIRouter()


@router.get("/map")
async def get_explore_map(
    lat:      Optional[float]  = Query(default=None, description="GPS latitude"),
    lng:      Optional[float]  = Query(default=None, description="GPS longitude"),
    radius:   float            = Query(default=15,   description="Search radius in km"),
    district: Optional[str]    = Query(default=None, description="District name (fallback when no GPS)"),
    filter:   str              = Query(default="all", description="Filter: all | workers | jobs | urgent | volunteer | no_exp"),
    db=Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    return await ExploreController.get_map(
        lat=lat,
        lng=lng,
        radius=radius,
        district=district,
        filter_type=filter,
        current_user_id=current_user_id,
        db=db,
    )
