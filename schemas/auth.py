from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict


class LoginRequest(BaseModel):
    identifier: str
    password: str


class UserResponse(BaseModel):
    id: str
    name: str
    username: str
    email: Optional[str] = None
    phone: Optional[str] = None
    photo_url: Optional[str] = None
    preferred_language: Optional[str] = None
    is_worker: bool
    trust_score: int
    trust_badge: str
    area_name: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    location_accuracy: Optional[str] = None

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class WorkerProfileSchema(BaseModel):
    skills: List[str] = []
    experience_levels: Dict[str, str] = {}
    availability_days: List[str] = []
    availability_slots: List[str] = []
    wage_min: Optional[int] = None
    wage_max: Optional[int] = None
    open_to_no_exp_jobs: bool = True
    feed_preferences: List[str] = []
    willing_to_travel: bool = False


class SignupRequest(BaseModel):
    # Step 1 — credentials
    name: str
    username: str
    email: Optional[str] = None
    phone: Optional[str] = None
    password: str

    # Step 2 — basic profile
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    preferred_language: str = "english"
    photo_url: Optional[str] = None

    # Step 3 — location
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    area_name: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    location_accuracy: str = "district_level"

    # Step 4 — worker flag
    is_worker: bool = False

    # Step 5 — worker details (only if is_worker true)
    worker_profile: Optional[WorkerProfileSchema] = None


class ReverseGeocodeRequest(BaseModel):
    latitude: float
    longitude: float

