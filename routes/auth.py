import os
import re
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, Cookie
from sqlalchemy.orm import Session
from typing import Optional

from database import get_db
from models.user import User, UserCredential, UserSession, UserVerification, UserAvatarCredits
from models.worker import WorkerProfile, WorkerRAGIndex
from schemas.auth import LoginRequest, TokenResponse, UserResponse, SignupRequest, WorkerProfileSchema
from utils.jwt import (
    verify_password,
    hash_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)

router = APIRouter(tags=["auth"])
language_router = APIRouter(tags=["language"])

# Read COOKIE_SECURE from env — defaults to False for local dev
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "False").lower() in ("true", "1", "yes")
REFRESH_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 30))


# ---------------------------------------------------------------------------
# POST /api/auth/login
# ---------------------------------------------------------------------------
@router.post("/login", response_model=TokenResponse)
async def login(request: Request, response: Response, body: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate a user by identifier (username/email/phone) and password.
    Returns an access token in the body and sets a httpOnly refresh token cookie.
    """
    now = datetime.utcnow()

    # 1. Look up credential row by login_identifier
    credential: Optional[UserCredential] = (
        db.query(UserCredential)
        .filter(UserCredential.login_identifier == body.identifier)
        .first()
    )
    if not credential:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # 2. Check credential is active
    if not credential.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    # 3. Check account lock
    if credential.locked_until and credential.locked_until > now:
        locked_str = credential.locked_until.strftime("%Y-%m-%d %H:%M:%S UTC")
        raise HTTPException(
            status_code=423,
            detail=f"Account locked. Try again after {locked_str}",
        )

    # 4. Verify password
    if not verify_password(body.password, credential.password_hash):
        credential.failed_attempts = (credential.failed_attempts or 0) + 1

        if credential.failed_attempts >= 5:
            credential.locked_until = now + timedelta(minutes=30)
            db.commit()
            raise HTTPException(
                status_code=423,
                detail="Too many failed attempts. Account locked for 30 minutes.",
            )

        db.commit()
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # 5. Password correct — reset failure tracking
    credential.failed_attempts = 0
    credential.locked_until = None
    credential.last_login_at = now
    db.commit()

    # 6. Load the user profile
    user: Optional[User] = db.query(User).filter(User.id == credential.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User profile not found")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account suspended")

    # 7. Generate tokens
    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))
    refresh_token_hash = hash_password(refresh_token)

    # 8. Persist the session
    session = UserSession(
        id=uuid.uuid4(),
        user_id=user.id,
        refresh_token_hash=refresh_token_hash,
        device_info=request.headers.get("user-agent", ""),
        ip_address=request.client.host if request.client else "unknown",
        is_active=True,
        expires_at=now + timedelta(days=REFRESH_EXPIRE_DAYS),
        created_at=now,
        last_used_at=now,
    )
    db.add(session)
    db.commit()

    # 9. Set httpOnly refresh token cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=REFRESH_EXPIRE_DAYS * 24 * 60 * 60,
    )

    # 10. Build and return the token response
    user_data = UserResponse(
        id=str(user.id),
        name=user.name or "",
        username=user.username or "",
        email=user.email,
        phone=user.phone,
        photo_url=user.photo_url,
        preferred_language=user.preferred_language,
        is_worker=user.is_worker or False,
        trust_score=user.trust_score or 0,
        trust_badge=user.trust_badge or "new",
        area_name=user.area_name,
        city=user.city,
    )

    return TokenResponse(access_token=access_token, token_type="bearer", user=user_data)


# ---------------------------------------------------------------------------
# POST /api/auth/refresh
# ---------------------------------------------------------------------------
@router.post("/refresh")
async def refresh(response: Response, refresh_token: Optional[str] = Cookie(default=None), db: Session = Depends(get_db)):
    """
    Issue a fresh access token using the httpOnly refresh token cookie.
    Also updates last_used_at on the matched session.
    """
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token")

    # Decode the refresh token to get user_id
    try:
        payload = decode_token(refresh_token)
        user_id = payload.get("sub")
        if not user_id or payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid session")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid session")

    # Find active sessions for this user and verify the token hash
    sessions = (
        db.query(UserSession)
        .filter(
            UserSession.user_id == user_id,
            UserSession.is_active == True,
            UserSession.expires_at > datetime.utcnow(),
        )
        .all()
    )

    matched_session: Optional[UserSession] = None
    for s in sessions:
        if verify_password(refresh_token, s.refresh_token_hash):
            matched_session = s
            break

    if not matched_session:
        raise HTTPException(status_code=401, detail="Invalid session")

    # Update last used timestamp
    matched_session.last_used_at = datetime.utcnow()
    db.commit()

    # Issue new access token
    new_access_token = create_access_token(user_id)
    return {"access_token": new_access_token, "token_type": "bearer"}


# ---------------------------------------------------------------------------
# POST /api/auth/logout
# ---------------------------------------------------------------------------
@router.post("/logout")
async def logout(response: Response, refresh_token: Optional[str] = Cookie(default=None), db: Session = Depends(get_db)):
    """
    Deactivate the current session and clear the refresh token cookie.
    """
    if refresh_token:
        try:
            payload = decode_token(refresh_token)
            user_id = payload.get("sub")

            if user_id:
                # Find and deactivate the matching session
                sessions = (
                    db.query(UserSession)
                    .filter(
                        UserSession.user_id == user_id,
                        UserSession.is_active == True,
                    )
                    .all()
                )
                for s in sessions:
                    if verify_password(refresh_token, s.refresh_token_hash):
                        s.is_active = False
                        db.commit()
                        break
        except Exception:
            # Even if the token is expired/invalid we still clear the cookie
            pass

    # Delete the cookie regardless
    response.delete_cookie(key="refresh_token", httponly=True, samesite="lax")
    return {"message": "Logged out successfully"}


# ---------------------------------------------------------------------------
# GET /api/auth/check-username
# ---------------------------------------------------------------------------
@router.get("/check-username")
async def check_username(username: str, db: Session = Depends(get_db)):
    if len(username) < 4 or not re.match(r"^[a-zA-Z0-9_]+$", username):
        return {"available": False, "message": "Invalid username format"}

    existing = (
        db.query(UserCredential)
        .filter(UserCredential.login_identifier == username)
        .first()
    )
    if existing:
        return {"available": False}
    return {"available": True}


# ---------------------------------------------------------------------------
# GET /api/language/{language_code}
# ---------------------------------------------------------------------------
@language_router.get("/language/{language_code}")
async def get_language(language_code: str):
    from utils.language import TRANSLATIONS
    if language_code in TRANSLATIONS:
        return TRANSLATIONS[language_code]
    return TRANSLATIONS["english"]


# ---------------------------------------------------------------------------
# POST /api/auth/signup
# ---------------------------------------------------------------------------
@router.post("/signup", response_model=TokenResponse)
async def signup(
    request: Request,
    response: Response,
    body: SignupRequest,
    db: Session = Depends(get_db),
):
    now = datetime.utcnow()

    # --- Validation checks ---
    # 1. name not empty
    if not body.name or not body.name.strip():
        raise HTTPException(status_code=400, detail="Name cannot be empty")

    # 2. username min 4 chars, alphanumeric only
    if len(body.username) < 4 or not re.match(r"^[a-zA-Z0-9_]+$", body.username):
        raise HTTPException(
            status_code=400,
            detail="Username must be at least 4 characters and contain only alphanumeric characters and underscores",
        )

    # 3. at least email or phone provided
    if not body.email and not body.phone:
        raise HTTPException(
            status_code=400,
            detail="At least one of email or phone is required",
        )

    # 4. password min 6 chars
    if len(body.password) < 6:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 6 characters",
        )

    # 5. if email provided — basic email format check
    if body.email:
        if not re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", body.email):
            raise HTTPException(
                status_code=400,
                detail="Invalid email format",
            )

    # 6. if phone provided — digits only, 10 digits
    if body.phone:
        if not re.match(r"^\d{10}$", body.phone):
            raise HTTPException(
                status_code=400,
                detail="Phone number must be exactly 10 digits",
            )

    # --- Uniqueness checks (conflict 409) ---
    # Query user_credentials where login_identifier = username
    existing_username = (
        db.query(UserCredential)
        .filter(UserCredential.login_identifier == body.username)
        .first()
    )
    if existing_username:
        raise HTTPException(status_code=409, detail="Username already taken")

    # If email provided -> query where login_identifier = email
    if body.email:
        existing_email = (
            db.query(UserCredential)
            .filter(UserCredential.login_identifier == body.email)
            .first()
        )
        if existing_email:
            raise HTTPException(status_code=409, detail="Email already registered")

    # If phone provided -> query where login_identifier = phone
    if body.phone:
        existing_phone = (
            db.query(UserCredential)
            .filter(UserCredential.login_identifier == body.phone)
            .first()
        )
        if existing_phone:
            raise HTTPException(status_code=409, detail="Phone already registered")

    # Parse date_of_birth if provided
    dob_date = None
    if body.date_of_birth:
        try:
            dob_date = datetime.strptime(body.date_of_birth, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="date_of_birth must be in YYYY-MM-DD format",
                )

    # Map gender input to database enum labels: 'male', 'female', 'prefer_not_to_say'
    gender_val = None
    if body.gender:
        val = body.gender.lower()
        if val in ("male", "female"):
            gender_val = val
        elif "prefer" in val or "not" in val or "say" in val:
            gender_val = "prefer_not_to_say"
        else:
            gender_val = val

    # --- Database Inserts ---
    # 1. Insert into users table
    new_user = User(
        id=uuid.uuid4(),
        name=body.name,
        username=body.username,
        phone=body.phone or None,
        email=body.email or None,
        photo_url=body.photo_url or None,
        date_of_birth=dob_date,
        gender=gender_val,
        preferred_language=body.preferred_language,
        latitude=str(body.latitude) if body.latitude is not None else None,
        longitude=str(body.longitude) if body.longitude is not None else None,
        area_name=body.area_name or None,
        city=body.city or None,
        state=body.state or None,
        district=body.district or None,
        location_accuracy=body.location_accuracy,
        is_worker=body.is_worker,
        trust_score=0,
        trust_badge="new",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(new_user)
    db.flush()

    # 2. Insert into user_credentials
    password_hash = hash_password(body.password)

    # Username credential (always)
    db.add(
        UserCredential(
            id=uuid.uuid4(),
            user_id=new_user.id,
            login_identifier=body.username,
            identifier_type="username",
            password_hash=password_hash,
            is_active=True,
            failed_attempts=0,
            created_at=now,
            updated_at=now,
        )
    )

    # Email credential if provided
    if body.email:
        db.add(
            UserCredential(
                id=uuid.uuid4(),
                user_id=new_user.id,
                login_identifier=body.email,
                identifier_type="email",
                password_hash=password_hash,
                is_active=True,
                failed_attempts=0,
                created_at=now,
                updated_at=now,
            )
        )

    # Phone credential if provided
    if body.phone:
        db.add(
            UserCredential(
                id=uuid.uuid4(),
                user_id=new_user.id,
                login_identifier=body.phone,
                identifier_type="phone",
                password_hash=password_hash,
                is_active=True,
                failed_attempts=0,
                created_at=now,
                updated_at=now,
            )
        )

    # 3. Insert into user_verifications
    db.add(
        UserVerification(
            id=uuid.uuid4(),
            user_id=new_user.id,
            aadhaar_number_hash=None,
            aadhaar_verified=False,
            aadhaar_verified_at=None,
            verification_attempt_count=0,
            updated_at=now,
        )
    )

    # 4. Insert into user_avatar_credits
    db.add(
        UserAvatarCredits(
            id=uuid.uuid4(),
            user_id=new_user.id,
            free_daily_credits_remaining=5,
            free_monthly_credits_remaining=20,
            purchased_credits_remaining=0,
            total_credits_used_lifetime=0,
            daily_reset_at=now,
            monthly_reset_at=now,
            updated_at=now,
        )
    )

    # 5. Insert into worker_profiles and worker_rag_index if is_worker is True
    if body.is_worker and body.worker_profile is not None:
        profile_data = body.worker_profile
        db.add(
            WorkerProfile(
                id=uuid.uuid4(),
                user_id=new_user.id,
                skills=profile_data.skills or [],
                experience_levels=profile_data.experience_levels or {},
                availability_days=profile_data.availability_days or [],
                availability_slots=profile_data.availability_slots or [],
                wage_min=profile_data.wage_min or None,
                wage_max=profile_data.wage_max or None,
                open_to_no_exp_jobs=profile_data.open_to_no_exp_jobs,
                feed_preferences=profile_data.feed_preferences or [],
                is_profile_complete=True,
                willing_to_travel=profile_data.willing_to_travel,
                updated_at=now,
            )
        )

        db.add(
            WorkerRAGIndex(
                id=uuid.uuid4(),
                worker_id=new_user.id,
                is_dirty=True,
                index_version=0,
                updated_at=now,
            )
        )

    db.commit()

    # --- Generate tokens and session ---
    access_token = create_access_token(str(new_user.id))
    refresh_token = create_refresh_token(str(new_user.id))
    refresh_token_hash = hash_password(refresh_token)

    session = UserSession(
        id=uuid.uuid4(),
        user_id=new_user.id,
        refresh_token_hash=refresh_token_hash,
        device_info=request.headers.get("user-agent", ""),
        ip_address=request.client.host if request.client else "unknown",
        is_active=True,
        expires_at=now + timedelta(days=30),
        created_at=now,
        last_used_at=now,
    )
    db.add(session)
    db.commit()

    # Set httpOnly refresh token cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=30 * 24 * 60 * 60,
    )

    # Build and return the token response
    user_data = UserResponse(
        id=str(new_user.id),
        name=new_user.name or "",
        username=new_user.username or "",
        email=new_user.email,
        phone=new_user.phone,
        photo_url=new_user.photo_url,
        preferred_language=new_user.preferred_language,
        is_worker=new_user.is_worker or False,
        trust_score=new_user.trust_score or 0,
        trust_badge=new_user.trust_badge or "new",
        area_name=new_user.area_name,
        city=new_user.city,
        district=new_user.district,
        location_accuracy=new_user.location_accuracy,
    )

    return TokenResponse(access_token=access_token, token_type="bearer", user=user_data)


# ---------------------------------------------------------------------------
# PATCH /api/users/me/preferences
# ---------------------------------------------------------------------------
from utils.dependencies import get_current_user
from pydantic import BaseModel

users_router = APIRouter(tags=["users"])

class PreferencesPatchRequest(BaseModel):
    tech_comfort_level: str

@users_router.get("/me")
async def get_current_user_profile(
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    """Return the authenticated user's full profile."""
    user = db.query(User).filter(User.id == current_user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": str(user.id),
        "name": user.name or "",
        "username": user.username or "",
        "email": user.email,
        "phone": user.phone,
        "photo_url": user.photo_url,
        "preferred_language": user.preferred_language,
        "is_worker": user.is_worker or False,
        "trust_score": user.trust_score or 0,
        "trust_badge": user.trust_badge or "new",
        "area_name": user.area_name,
        "city": user.city,
        "state": user.state,
        "district": user.district,
        "tech_comfort_level": user.tech_comfort_level,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


@users_router.patch("/me/preferences")
async def update_preferences(
    body: PreferencesPatchRequest,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    user = db.query(User).filter(User.id == current_user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user.tech_comfort_level = body.tech_comfort_level
    user.updated_at = datetime.utcnow()
    db.commit()
    
    return {"status": "success", "tech_comfort_level": user.tech_comfort_level}
